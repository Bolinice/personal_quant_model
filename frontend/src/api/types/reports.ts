export interface Report {
  id: number;
  title: string;
  report_type: string;
  report_date: string | null;
  model_id: number | null;
  backtest_id: number | null;
  content: string | null;
  summary: string | null;
  file_path: string | null;
  file_format: string | null;
  status: string;
  meta_json: Record<string, unknown> | null;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}
