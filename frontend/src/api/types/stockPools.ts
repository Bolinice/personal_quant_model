export interface StockPool {
  id: number;
  pool_code: string;
  pool_name: string;
  pool_type: string | null;
  base_index_code: string | null;
  filter_config: Record<string, unknown> | null;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
