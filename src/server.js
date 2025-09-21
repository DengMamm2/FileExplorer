const express = require('express');
const fs = require('fs').promises;
const path = require('path');
const sharp = require('sharp');
const WebSocket = require('ws');
const mime = require('mime-types');
const http = require('http');

class PerformantFileExplorer {
  constructor() {
    this.app = express();
    this.server = http.createServer(this.app);
    this.wss = new WebSocket.Server({ server: this.server });
    this.thumbnailCache = new Map();
    this.directoryCache = new Map();
    this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
    
    this.setupMiddleware();
    this.setupRoutes();
    this.setupWebSocket();
    this.setupThumbnailCleanup();
  }

  setupMiddleware() {
    this.app.use(express.static('public'));
    this.app.use(express.json());
    
    // Create thumbnails directory if it doesn't exist
    this.ensureDirectoryExists('./thumbnails');
  }

  async ensureDirectoryExists(dirPath) {
    try {
      await fs.access(dirPath);
    } catch {
      await fs.mkdir(dirPath, { recursive: true });
    }
  }

  setupRoutes() {
    // Serve the main page
    this.app.get('/', (req, res) => {
      res.sendFile(path.join(__dirname, '../public/index.html'));
    });

    // API to get directory contents with pagination and lazy loading
    this.app.get('/api/directory', async (req, res) => {
      try {
        const dirPath = req.query.path || process.cwd();
        const page = parseInt(req.query.page) || 0;
        const limit = parseInt(req.query.limit) || 50;
        const includeThumbnails = req.query.thumbnails === 'true';

        const result = await this.getDirectoryContents(dirPath, page, limit, includeThumbnails);
        res.json(result);
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    });

    // API to get optimized thumbnail
    this.app.get('/api/thumbnail/:encodedPath', async (req, res) => {
      try {
        const filePath = decodeURIComponent(req.params.encodedPath);
        const size = parseInt(req.query.size) || 200;
        
        const thumbnail = await this.getOptimizedThumbnail(filePath, size);
        
        res.set('Content-Type', 'image/jpeg');
        res.set('Cache-Control', 'public, max-age=86400'); // Cache for 24 hours
        res.send(thumbnail);
      } catch (error) {
        res.status(404).json({ error: 'Thumbnail not available' });
      }
    });

    // API to get file metadata without loading the full file
    this.app.get('/api/metadata/:encodedPath', async (req, res) => {
      try {
        const filePath = decodeURIComponent(req.params.encodedPath);
        const metadata = await this.getFileMetadata(filePath);
        res.json(metadata);
      } catch (error) {
        res.status(500).json({ error: error.message });
      }
    });
  }

  setupWebSocket() {
    this.wss.on('connection', (ws) => {
      console.log('Client connected for real-time updates');
      
      ws.on('message', async (message) => {
        try {
          const data = JSON.parse(message);
          
          if (data.type === 'scan_directory') {
            await this.scanDirectoryAsync(data.path, ws);
          }
        } catch (error) {
          ws.send(JSON.stringify({ type: 'error', message: error.message }));
        }
      });
    });
  }

  async getDirectoryContents(dirPath, page = 0, limit = 50, includeThumbnails = false) {
    // Check cache first
    const cacheKey = `${dirPath}:${page}:${limit}:${includeThumbnails}`;
    if (this.directoryCache.has(cacheKey)) {
      const cached = this.directoryCache.get(cacheKey);
      if (Date.now() - cached.timestamp < this.cacheTimeout) {
        return cached.data;
      }
    }

    const items = await fs.readdir(dirPath, { withFileTypes: true });
    const total = items.length;
    const startIndex = page * limit;
    const endIndex = Math.min(startIndex + limit, total);
    const pageItems = items.slice(startIndex, endIndex);

    const result = {
      path: dirPath,
      total,
      page,
      limit,
      hasMore: endIndex < total,
      items: []
    };

    // Process items in parallel for better performance
    const processPromises = pageItems.map(async (item) => {
      const itemPath = path.join(dirPath, item.name);
      const stats = await fs.stat(itemPath);
      
      const fileItem = {
        name: item.name,
        path: itemPath,
        isDirectory: item.isDirectory(),
        size: stats.size,
        modified: stats.mtime,
        type: this.getFileType(item.name)
      };

      // Only generate thumbnails for supported image/video files if requested
      if (includeThumbnails && !item.isDirectory() && this.isMediaFile(item.name)) {
        try {
          fileItem.hasThumbnail = true;
          fileItem.thumbnailUrl = `/api/thumbnail/${encodeURIComponent(itemPath)}?size=200`;
        } catch {
          fileItem.hasThumbnail = false;
        }
      }

      return fileItem;
    });

    result.items = await Promise.all(processPromises);

    // Cache the result
    this.directoryCache.set(cacheKey, {
      data: result,
      timestamp: Date.now()
    });

    return result;
  }

  async getOptimizedThumbnail(filePath, size = 200) {
    const cacheKey = `${filePath}:${size}`;
    
    // Check memory cache first
    if (this.thumbnailCache.has(cacheKey)) {
      return this.thumbnailCache.get(cacheKey);
    }

    // Check disk cache
    const thumbnailPath = path.join('./thumbnails', `${Buffer.from(cacheKey).toString('base64')}.jpg`);
    
    try {
      const cachedThumbnail = await fs.readFile(thumbnailPath);
      this.thumbnailCache.set(cacheKey, cachedThumbnail);
      return cachedThumbnail;
    } catch {
      // Generate new thumbnail
    }

    let thumbnail;
    
    if (this.isImageFile(filePath)) {
      thumbnail = await sharp(filePath)
        .resize(size, size, { 
          fit: 'cover',
          position: 'center'
        })
        .jpeg({ 
          quality: 80,
          progressive: true
        })
        .toBuffer();
    } else {
      // For non-image files, create a placeholder or use file type icon
      thumbnail = await this.generatePlaceholderThumbnail(filePath, size);
    }

    // Cache to disk and memory
    await fs.writeFile(thumbnailPath, thumbnail);
    this.thumbnailCache.set(cacheKey, thumbnail);

    // Limit memory cache size
    if (this.thumbnailCache.size > 100) {
      const firstKey = this.thumbnailCache.keys().next().value;
      this.thumbnailCache.delete(firstKey);
    }

    return thumbnail;
  }

  async generatePlaceholderThumbnail(filePath, size) {
    const fileType = this.getFileType(filePath);
    const color = this.getTypeColor(fileType);
    
    return sharp({
      create: {
        width: size,
        height: size,
        channels: 4,
        background: color
      }
    })
    .png()
    .toBuffer();
  }

  getTypeColor(fileType) {
    const colors = {
      'video': { r: 255, g: 99, b: 71, alpha: 1 },
      'audio': { r: 135, g: 206, b: 235, alpha: 1 },
      'document': { r: 144, g: 238, b: 144, alpha: 1 },
      'archive': { r: 255, g: 215, b: 0, alpha: 1 },
      'unknown': { r: 169, g: 169, b: 169, alpha: 1 }
    };
    return colors[fileType] || colors.unknown;
  }

  async getFileMetadata(filePath) {
    const stats = await fs.stat(filePath);
    const fileType = this.getFileType(filePath);
    
    return {
      name: path.basename(filePath),
      path: filePath,
      size: stats.size,
      sizeFormatted: this.formatFileSize(stats.size),
      modified: stats.mtime,
      type: fileType,
      isDirectory: stats.isDirectory(),
      extension: path.extname(filePath).toLowerCase()
    };
  }

  async scanDirectoryAsync(dirPath, ws) {
    try {
      ws.send(JSON.stringify({ type: 'scan_start', path: dirPath }));
      
      const items = await fs.readdir(dirPath, { withFileTypes: true });
      const batchSize = 20;
      
      for (let i = 0; i < items.length; i += batchSize) {
        const batch = items.slice(i, i + batchSize);
        const batchResults = await Promise.all(
          batch.map(async (item) => {
            const itemPath = path.join(dirPath, item.name);
            const stats = await fs.stat(itemPath);
            
            return {
              name: item.name,
              path: itemPath,
              isDirectory: item.isDirectory(),
              size: stats.size,
              modified: stats.mtime,
              type: this.getFileType(item.name)
            };
          })
        );
        
        ws.send(JSON.stringify({
          type: 'scan_batch',
          items: batchResults,
          progress: Math.round(((i + batch.length) / items.length) * 100)
        }));
        
        // Small delay to prevent overwhelming the client
        await new Promise(resolve => setTimeout(resolve, 10));
      }
      
      ws.send(JSON.stringify({ type: 'scan_complete' }));
    } catch (error) {
      ws.send(JSON.stringify({ type: 'scan_error', message: error.message }));
    }
  }

  isMediaFile(filename) {
    return this.isImageFile(filename) || this.isVideoFile(filename);
  }

  isImageFile(filename) {
    const imageExts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'];
    return imageExts.includes(path.extname(filename).toLowerCase());
  }

  isVideoFile(filename) {
    const videoExts = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'];
    return videoExts.includes(path.extname(filename).toLowerCase());
  }

  getFileType(filename) {
    const ext = path.extname(filename).toLowerCase();
    
    if (['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg'].includes(ext)) {
      return 'image';
    }
    if (['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'].includes(ext)) {
      return 'video';
    }
    if (['.mp3', '.wav', '.flac', '.aac', '.ogg'].includes(ext)) {
      return 'audio';
    }
    if (['.txt', '.doc', '.docx', '.pdf', '.rtf'].includes(ext)) {
      return 'document';
    }
    if (['.zip', '.rar', '.7z', '.tar', '.gz'].includes(ext)) {
      return 'archive';
    }
    
    return 'unknown';
  }

  formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  setupThumbnailCleanup() {
    // Clean up old thumbnails every hour
    setInterval(async () => {
      try {
        const thumbnailDir = './thumbnails';
        const files = await fs.readdir(thumbnailDir);
        const now = Date.now();
        
        for (const file of files) {
          const filePath = path.join(thumbnailDir, file);
          const stats = await fs.stat(filePath);
          
          // Delete thumbnails older than 24 hours
          if (now - stats.mtime.getTime() > 24 * 60 * 60 * 1000) {
            await fs.unlink(filePath);
          }
        }
      } catch (error) {
        console.error('Thumbnail cleanup error:', error);
      }
    }, 60 * 60 * 1000); // Every hour
  }

  start(port = 3000) {
    this.server.listen(port, () => {
      console.log(`FileExplorer server running on http://localhost:${port}`);
    });
  }
}

// Start the server only if not in test mode
if (require.main === module) {
  const fileExplorer = new PerformantFileExplorer();
  fileExplorer.start();
}

module.exports = PerformantFileExplorer;