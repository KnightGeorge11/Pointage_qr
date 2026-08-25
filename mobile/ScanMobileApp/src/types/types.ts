export interface Site {
  id: number;
  nom: string;
  name: string;
  adresse?: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
}
  
  export interface Employee {
    id: number;
    qr_code: string;
    name: string;
    department?: string;
  }
  
  export interface ScanRecord {
    id?: number;
    employee_qr: string;
    site_id: number;
    timestamp: string;
    mode?: 'normal' | 'garde';
    is_first_scan: boolean;
  }
  
  export interface ApiResponse<T> {
    data: T;
    message?: string;
    status: 'success' | 'error';
  }