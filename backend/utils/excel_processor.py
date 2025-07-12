import pandas as pd
import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import os


class ExcelDataProcessor:
    """Utility class for processing Excel files and extracting metadata"""
    
    def __init__(self):
        self.supported_formats = {'.xlsx', '.xls', '.csv'}
    
    def analyze_file(self, file_path: str) -> Dict:
        """Analyze an Excel/CSV file and extract metadata"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {file_ext}")
        
        try:
            if file_ext == '.csv':
                return self._analyze_csv(file_path)
            else:
                return self._analyze_excel(file_path)
        except Exception as e:
            raise Exception(f"Error analyzing file: {str(e)}")
    
    def _analyze_excel(self, file_path: str) -> Dict:
        """Analyze Excel file with multiple sheets"""
        excel_file = pd.ExcelFile(file_path)
        file_info = {
            'file_path': file_path,
            'file_size': os.path.getsize(file_path),
            'sheets': [],
            'total_rows': 0,
            'total_columns': 0,
            'analysis_date': datetime.utcnow().isoformat()
        }
        
        for sheet_name in excel_file.sheet_names:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                sheet_info = self._analyze_dataframe(df, sheet_name)
                file_info['sheets'].append(sheet_info)
                file_info['total_rows'] += sheet_info['row_count']
                file_info['total_columns'] += sheet_info['column_count']
            except Exception as e:
                file_info['sheets'].append({
                    'name': sheet_name,
                    'error': f"Could not analyze sheet: {str(e)}"
                })
        
        return file_info
    
    def _analyze_csv(self, file_path: str) -> Dict:
        """Analyze CSV file"""
        df = pd.read_csv(file_path)
        sheet_info = self._analyze_dataframe(df, 'Sheet1')
        
        return {
            'file_path': file_path,
            'file_size': os.path.getsize(file_path),
            'sheets': [sheet_info],
            'total_rows': sheet_info['row_count'],
            'total_columns': sheet_info['column_count'],
            'analysis_date': datetime.utcnow().isoformat()
        }
    
    def _analyze_dataframe(self, df: pd.DataFrame, sheet_name: str) -> Dict:
        """Analyze a pandas DataFrame and extract metadata"""
        # Basic info
        sheet_info = {
            'name': sheet_name,
            'row_count': len(df),
            'column_count': len(df.columns),
            'columns': [],
            'data_quality': {
                'completeness': 0,
                'null_count': 0,
                'duplicate_rows': 0
            },
            'preview': []
        }
        
        # Analyze each column
        for col in df.columns:
            col_info = self._analyze_column(df[col], col)
            sheet_info['columns'].append(col_info)
        
        # Data quality metrics
        total_cells = len(df) * len(df.columns)
        null_count = df.isnull().sum().sum()
        sheet_info['data_quality']['null_count'] = int(null_count)
        sheet_info['data_quality']['completeness'] = round(
            ((total_cells - null_count) / total_cells * 100) if total_cells > 0 else 0, 2
        )
        sheet_info['data_quality']['duplicate_rows'] = int(df.duplicated().sum())
        
        # Preview data (first 5 rows)
        if len(df) > 0:
            preview_df = df.head(5)
            sheet_info['preview'] = preview_df.to_dict('records')
        
        return sheet_info
    
    def _analyze_column(self, series: pd.Series, column_name: str) -> Dict:
        """Analyze a pandas Series (column) and extract metadata"""
        col_info = {
            'name': column_name,
            'data_type': str(series.dtype),
            'non_null_count': int(series.count()),
            'null_count': int(series.isnull().sum()),
            'null_percentage': round((series.isnull().sum() / len(series) * 100) if len(series) > 0 else 0, 2),
            'unique_count': int(series.nunique()),
            'is_unique': series.nunique() == len(series),
            'contains_pii': self._detect_pii(series, column_name)
        }
        
        # Type-specific analysis
        if series.dtype in ['int64', 'float64']:
            col_info.update(self._analyze_numeric_column(series))
        elif series.dtype == 'object':
            col_info.update(self._analyze_text_column(series))
        elif series.dtype == 'datetime64[ns]':
            col_info.update(self._analyze_datetime_column(series))
        
        return col_info
    
    def _analyze_numeric_column(self, series: pd.Series) -> Dict:
        """Analyze numeric column"""
        try:
            return {
                'min_value': float(series.min()) if not series.empty else None,
                'max_value': float(series.max()) if not series.empty else None,
                'mean_value': round(float(series.mean()), 2) if not series.empty else None,
                'median_value': float(series.median()) if not series.empty else None,
                'std_value': round(float(series.std()), 2) if not series.empty else None
            }
        except:
            return {}
    
    def _analyze_text_column(self, series: pd.Series) -> Dict:
        """Analyze text column"""
        try:
            non_null_series = series.dropna()
            if non_null_series.empty:
                return {}
            
            return {
                'min_length': int(non_null_series.astype(str).str.len().min()),
                'max_length': int(non_null_series.astype(str).str.len().max()),
                'avg_length': round(float(non_null_series.astype(str).str.len().mean()), 2),
                'most_common': list(series.value_counts().head(5).to_dict().keys())
            }
        except:
            return {}
    
    def _analyze_datetime_column(self, series: pd.Series) -> Dict:
        """Analyze datetime column"""
        try:
            non_null_series = series.dropna()
            if non_null_series.empty:
                return {}
            
            return {
                'min_date': non_null_series.min().isoformat() if hasattr(non_null_series.min(), 'isoformat') else str(non_null_series.min()),
                'max_date': non_null_series.max().isoformat() if hasattr(non_null_series.max(), 'isoformat') else str(non_null_series.max()),
                'date_range_days': (non_null_series.max() - non_null_series.min()).days if len(non_null_series) > 0 else 0
            }
        except:
            return {}
    
    def _detect_pii(self, series: pd.Series, column_name: str) -> bool:
        """Detect potential PII based on column name and content patterns"""
        pii_indicators = [
            'email', 'phone', 'ssn', 'social', 'passport', 'license',
            'address', 'name', 'firstname', 'lastname', 'surname',
            'dob', 'birthdate', 'birth_date', 'credit_card', 'account'
        ]
        
        # Check column name
        column_lower = column_name.lower()
        if any(indicator in column_lower for indicator in pii_indicators):
            return True
        
        # Check content patterns (sample first 100 non-null values)
        try:
            sample_data = series.dropna().head(100).astype(str)
            if sample_data.empty:
                return False
            
            # Email pattern
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            if sample_data.str.contains(email_pattern, regex=True).any():
                return True
            
            # Phone pattern (basic)
            phone_pattern = r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
            if sample_data.str.contains(phone_pattern, regex=True).any():
                return True
            
            # SSN pattern (US)
            ssn_pattern = r'\d{3}-\d{2}-\d{4}'
            if sample_data.str.contains(ssn_pattern, regex=True).any():
                return True
        
        except:
            pass
        
        return False
    
    def generate_asset_metadata(self, file_analysis: Dict, asset_name: str = None) -> Dict:
        """Generate data asset metadata from file analysis"""
        if not asset_name:
            asset_name = os.path.splitext(os.path.basename(file_analysis['file_path']))[0]
        
        # Generate schema info
        schema_info = {
            'sheets': []
        }
        
        for sheet in file_analysis['sheets']:
            if 'error' in sheet:
                continue
            
            sheet_schema = {
                'name': sheet['name'],
                'columns': [
                    {
                        'name': col['name'],
                        'data_type': col['data_type'],
                        'nullable': col['null_count'] > 0,
                        'unique': col['is_unique'],
                        'contains_pii': col['contains_pii']
                    } for col in sheet['columns']
                ]
            }
            schema_info['sheets'].append(sheet_schema)
        
        # Generate tags based on analysis
        tags = []
        if any(sheet.get('data_quality', {}).get('completeness', 0) > 95 for sheet in file_analysis['sheets']):
            tags.append('high-quality')
        
        if any(col.get('contains_pii', False) for sheet in file_analysis['sheets'] 
               for col in sheet.get('columns', [])):
            tags.append('contains-pii')
        
        if file_analysis['total_rows'] > 10000:
            tags.append('large-dataset')
        
        # Calculate overall data quality score
        quality_scores = [sheet.get('data_quality', {}).get('completeness', 0) 
                         for sheet in file_analysis['sheets'] if 'error' not in sheet]
        data_quality_score = sum(quality_scores) / len(quality_scores) / 100 if quality_scores else 0
        
        return {
            'asset_name': asset_name,
            'description': f"Data asset generated from {os.path.basename(file_analysis['file_path'])}",
            'source_system': 'Excel/CSV Import',
            'source_location': file_analysis['file_path'],
            'schema_info': schema_info,
            'metadata': {
                'file_analysis': file_analysis,
                'import_date': datetime.utcnow().isoformat(),
                'row_count': file_analysis['total_rows'],
                'column_count': file_analysis['total_columns'],
                'sheet_count': len([s for s in file_analysis['sheets'] if 'error' not in s])
            },
            'tags': tags,
            'data_quality_score': round(data_quality_score, 3),
            'is_sensitive': any(col.get('contains_pii', False) for sheet in file_analysis['sheets'] 
                              for col in sheet.get('columns', [])),
            'access_level': 'Restricted' if any(col.get('contains_pii', False) for sheet in file_analysis['sheets'] 
                                               for col in sheet.get('columns', [])) else 'Internal'
        }
    
    def validate_file_for_import(self, file_path: str) -> Tuple[bool, List[str]]:
        """Validate file for import and return any issues"""
        issues = []
        
        if not os.path.exists(file_path):
            return False, ["File does not exist"]
        
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in self.supported_formats:
            issues.append(f"Unsupported file format: {file_ext}")
        
        file_size = os.path.getsize(file_path)
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            issues.append(f"File too large: {file_size / 1024 / 1024:.1f}MB (max: {max_size / 1024 / 1024}MB)")
        
        try:
            # Try to read the file
            if file_ext == '.csv':
                pd.read_csv(file_path, nrows=1)
            else:
                pd.read_excel(file_path, nrows=1)
        except Exception as e:
            issues.append(f"File read error: {str(e)}")
        
        return len(issues) == 0, issues