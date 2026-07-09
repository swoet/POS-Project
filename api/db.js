const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

module.exports = async (req, res) => {
  if (!process.env.DATABASE_URL) {
    return res.status(500).json({ error: 'DATABASE_URL not configured.' });
  }

  const { method, body, query } = req;
  const appId = query.appId || req.headers['x-app-id'];
  const collection = query.collection;

  if (!appId || !collection) {
    return res.status(400).json({ error: 'Missing appId or collection parameter.' });
  }

  try {
    if (method === 'GET') {
      const { rows } = await pool.query(
        'SELECT id, data, created_at FROM multidollar_data WHERE app_id = $1 AND collection = $2 ORDER BY created_at DESC',
        [appId, collection]
      );
      return res.status(200).json(rows);
    } 
    
    if (method === 'POST') {
      const { rows } = await pool.query(
        'INSERT INTO multidollar_data (app_id, collection, data) VALUES ($1, $2, $3) RETURNING id, data, created_at',
        [appId, collection, body]
      );
      return res.status(201).json(rows[0]);
    }
    
    if (method === 'PUT') {
      const id = query.id;
      if (!id) return res.status(400).json({ error: 'Missing document id for PUT' });
      const { rows } = await pool.query(
        'UPDATE multidollar_data SET data = $1 WHERE id = $2 AND app_id = $3 RETURNING id, data, created_at',
        [body, id, appId]
      );
      return res.status(200).json(rows[0]);
    }
    
    if (method === 'DELETE') {
      const id = query.id;
      if (!id) return res.status(400).json({ error: 'Missing document id for DELETE' });
      await pool.query('DELETE FROM multidollar_data WHERE id = $1 AND app_id = $2', [id, appId]);
      return res.status(204).send();
    }

    return res.status(405).json({ error: 'Method Not Allowed' });
  } catch (error) {
    console.error('DB Error:', error);
    return res.status(500).json({ error: 'Internal Server Error', details: error.message });
  }
};
