import "server-only";
import { Pool } from "pg";

// A single pooled connection, reused across requests in dev (Next.js HMR would
// otherwise create a new Pool on every reload).
const globalForPg = globalThis as unknown as { pgPool?: Pool };

export const pool =
  globalForPg.pgPool ??
  new Pool({
    connectionString: process.env.DATABASE_URL,
    // Supabase requires TLS. The pooler cert isn't in Node's default CA store,
    // so don't reject it.
    ssl: { rejectUnauthorized: false },
    // Use Supabase's transaction pooler (port 6543) with this. Keep the local
    // pool small and release idle connections quickly so serverless instances
    // don't hoard them.
    max: 3,
    idleTimeoutMillis: 10_000,
  });

if (process.env.NODE_ENV !== "production") globalForPg.pgPool = pool;

export async function query<T = Record<string, unknown>>(
  text: string,
  params?: unknown[],
): Promise<T[]> {
  const res = await pool.query(text, params);
  return res.rows as T[];
}
