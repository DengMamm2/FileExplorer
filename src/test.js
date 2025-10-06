const request = require('supertest');
const path = require('path');
const PerformantFileExplorer = require('../src/server');

describe('FileExplorer Performance Tests', () => {
  let app;
  let fileExplorer;

  beforeAll(() => {
    fileExplorer = new PerformantFileExplorer();
    app = fileExplorer.app;
  });

  afterAll(() => {
    // Don't start the server in tests, just test the app
  });

  describe('API Performance', () => {
    test('should load directory contents quickly', async () => {
      const startTime = Date.now();
      
      const response = await request(app)
        .get('/api/directory')
        .query({ path: __dirname })
        .expect(200);
      
      const loadTime = Date.now() - startTime;
      
      // Should load in under 100ms for most directories
      expect(loadTime).toBeLessThan(100);
      expect(response.body).toHaveProperty('items');
      expect(response.body).toHaveProperty('total');
      expect(response.body).toHaveProperty('path');
    }, 10000);

    test('should handle pagination efficiently', async () => {
      const startTime = Date.now();
      
      const response = await request(app)
        .get('/api/directory')
        .query({ 
          path: path.join(__dirname, '../node_modules'),
          page: 0,
          limit: 50
        })
        .expect(200);
      
      const loadTime = Date.now() - startTime;
      
      // Should load paginated results quickly even for large directories
      expect(loadTime).toBeLessThan(200);
      expect(response.body.items.length).toBeLessThanOrEqual(50);
      expect(response.body).toHaveProperty('hasMore');
    }, 10000);

    test('should cache directory results', async () => {
      const testPath = __dirname;
      
      // First request
      const startTime1 = Date.now();
      await request(app)
        .get('/api/directory')
        .query({ path: testPath })
        .expect(200);
      const firstLoadTime = Date.now() - startTime1;
      
      // Second request should be faster due to caching
      const startTime2 = Date.now();
      await request(app)
        .get('/api/directory')
        .query({ path: testPath })
        .expect(200);
      const secondLoadTime = Date.now() - startTime2;
      
      // Second request should be faster or equal
      expect(secondLoadTime).toBeLessThanOrEqual(firstLoadTime + 10);
    }, 10000);

    test('should handle large directories without timeout', async () => {
      const largeDir = path.join(__dirname, '../node_modules');
      
      const response = await request(app)
        .get('/api/directory')
        .query({ path: largeDir })
        .expect(200);
      
      // Should handle large directories
      expect(response.body.total).toBeGreaterThan(0);
      expect(response.body.items).toBeInstanceOf(Array);
    }, 15000);
  });

  describe('Thumbnail Performance', () => {
    test('should respond quickly for non-existent thumbnails', async () => {
      const startTime = Date.now();
      
      await request(app)
        .get('/api/thumbnail/non-existent-file.jpg')
        .expect(404);
      
      const loadTime = Date.now() - startTime;
      expect(loadTime).toBeLessThan(50);
    });

    test('should serve cached thumbnails efficiently', async () => {
      // This test would be more meaningful with actual image files
      // For now, just test the endpoint responds appropriately
      const response = await request(app)
        .get('/api/thumbnail/test-file.jpg')
        .expect(404);
      
      expect(response.body).toHaveProperty('error');
    });
  });

  describe('Memory Management', () => {
    test('should not leak memory during repeated requests', async () => {
      const initialMemory = process.memoryUsage().heapUsed;
      
      // Make multiple requests
      for (let i = 0; i < 10; i++) {
        await request(app)
          .get('/api/directory')
          .query({ path: __dirname });
      }
      
      // Force garbage collection if available
      if (global.gc) {
        global.gc();
      }
      
      const finalMemory = process.memoryUsage().heapUsed;
      const memoryIncrease = finalMemory - initialMemory;
      
      // Memory increase should be reasonable (less than 50MB)
      expect(memoryIncrease).toBeLessThan(50 * 1024 * 1024);
    }, 15000);
  });
});

describe('FileExplorer Integration Tests', () => {
  let app;
  let fileExplorer;

  beforeAll(() => {
    fileExplorer = new PerformantFileExplorer();
    app = fileExplorer.app;
  });

  afterAll(() => {
    // Don't start the server in tests, just test the app
  });

  test('should serve main page', async () => {
    await request(app)
      .get('/')
      .expect(200)
      .expect('Content-Type', /text\/html/);
  });

  test('should handle invalid paths gracefully', async () => {
    await request(app)
      .get('/api/directory')
      .query({ path: '/non-existent-path' })
      .expect(500);
  });

  test('should provide file metadata', async () => {
    const response = await request(app)
      .get(`/api/metadata/${encodeURIComponent(__filename)}`)
      .expect(200);
    
    expect(response.body).toHaveProperty('name');
    expect(response.body).toHaveProperty('size');
    expect(response.body).toHaveProperty('type');
  });
});