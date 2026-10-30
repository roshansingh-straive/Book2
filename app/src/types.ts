export interface BoundingBox {
  top: number;
  left: number;
  width: number;
  height: number;
  shelf_tier?: number;
}

export interface ShelfItem {
  id: string;
  title: string;
  author: string | null;
  confidence: number | null;
  box: BoundingBox | null;
  box_source?: 'unavailable' | 'model_estimate';
  verification_status?: 'verified' | 'needs_review' | 'benchmark_replay' | 'single_pass';
  visible_text?: string;
  title_status?: 'agreed' | 'single_read' | 'uncertain';
  position_status?: 'agreed' | 'needs_review' | 'estimated';
  catalogue_title?: string | null;
  catalogue_status?: 'matched' | 'unlisted' | 'needs_review';
  review_reasons?: string[];
  title_variants?: string[];
  unconfirmed_variants?: string[];
  related_title?: string;
  exclusion_reason?: 'placeholder' | 'author_only' | 'uncertain_text' | 'possible_duplicate';
  status: 'matched' | 'misplaced' | 'unexpected' | 'needs_review';
  status_label: string;
  misplaced_reason?: string | null;
  target_bay_name?: string | null;
  sku?: string | null;
  price?: number;
}

export interface PlanogramItem {
  sku: string;
  title: string;
  author: string | null;
  assigned_bay_id: string;
  price: number;
  sales_velocity_units_per_day: number;
  simulated_on_hand: number;
  system_status: string;
  physically_on_shelf: boolean;
  days_since_stockout?: number;
}

export interface MissingItem {
  sku: string;
  title: string;
  author: string | null;
  planogram_bay_id: string;
  simulated_on_hand: number;
  price: number;
  sales_velocity: number;
  is_phantom_inventory: boolean;
  reason: string;
  action: string;
}

export interface ActionTask {
  id: string;
  type: 'missing_item' | 'misplaced_item' | 'record_error' | 'recognition_review';
  severity: 'critical' | 'warning' | 'high' | 'medium';
  badge: string;
  title: string;
  author: string | null;
  sku?: string;
  headline: string;
  suggested_action: string;
  system_on_hand?: number;
  shelf_count?: number;
  resolved?: boolean;
  shelf_item_id?: string;
  requires_review?: boolean;
}

export interface ScanMetrics {
  planogram_expected_items: number;
  shelf_items_detected: number;
  matched_count: number;
  missing_count: number;
  misplaced_count: number;
  review_count?: number;
  catalogue_matched_count?: number;
  independent_verified_count?: number;
  location_review_count?: number;
  provisional_count?: number;
  planogram_compliance_pct: number;
}

export interface ScanResult {
  bay_id: string;
  bay_code: string;
  bay_name: string;
  photo_filename: string;
  photo_url: string;
  scanned_at: string | null;
  mode: 'replay' | 'live';
  source_kind?: 'upload' | 'sample';
  upload_id?: string | null;
  model: string;
  effort: string;
  inference_duration_seconds: number | null;
  tokens_used: number | null;
  estimated_cost_usd: number | null;
  disclosure?: string;
  selection_reason?: string;
  run_id?: string;
  comparison_version?: number;
  reading_mode?: 'single_pass' | 'verified';
  unresolved_readings?: Array<Pick<ShelfItem, 'title' | 'visible_text' | 'exclusion_reason' | 'related_title'>>;
  candidate_cleanup?: { input_groups: number; displayed_titles: number; unresolved_groups: number; merged_alias_groups: number };
  comparison_suggestion?: { bay_id: string; bay_name: string; matching_titles: number; message: string } | null;
  source?: { source_path: string; interface: string; original_mode: string; source_date: string | null };
  harness?: { tile_count: number; calls_completed: number; rejected_readings?: number; unlocated_readings?: number; rotated_verification: boolean };
  metrics: ScanMetrics;
  planogram_items: PlanogramItem[];
  shelf_items: ShelfItem[];
  missing_items: MissingItem[];
  misplaced_items: ShelfItem[];
  action_tasks: ActionTask[];
}

export interface ScanProgress {
  step: number;
  status: string;
  message?: string;
  code?: string;
  reading_mode?: 'single_pass' | 'verified';
  completed_calls?: number;
  total_calls?: number;
  total_checks?: number;
  model?: string;
  result?: ScanResult;
}

export interface ScanHealth {
  upload_analysis_available?: boolean;
  inference_authentication_required?: boolean;
  live_available_by_difficulty: Record<string, boolean>;
}

export interface UploadedPhoto {
  upload_id: string;
  filename: string;
  photo_url: string;
  width: number;
  height: number;
  byte_size: number;
}

export interface Bay {
  id: string;
  code: string;
  name: string;
  photo?: string;
  aisle: string;
  section: string;
  difficulty?: string;
  scannable?: boolean;
  status: 'healthy' | 'action_needed' | 'unscanned';
  scanned_today?: boolean;
  last_scanned_at?: string;
  open_exceptions?: number;
  sales_at_risk?: number;
  expected_items_count?: number;
  ground_truth_items_count?: number;
  catalogue_skus?: string[];
}

export interface StoreData {
  store_name: string;
  store_id: string;
  description: string;
  disclaimer: string;
  total_bays: number;
  scannable_bays_count: number;
  bays: Bay[];
  catalogue: Record<string, PlanogramItem>;
  initial_inventory: Record<string, number>;
  summary: {
    on_shelf_availability_pct: number;
    open_exceptions_total: number;
    bays_scanned_today: number;
  };
}
