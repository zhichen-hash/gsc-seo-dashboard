"""
Google Search Console API 集成模块
"""
import os
import pickle
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import pandas as pd
import json

# API 权限范围
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']

class GSCClient:
    """Google Search Console API 客户端"""

    def __init__(self):
        """初始化 GSC 客户端"""
        self.service = None
        self._authenticate()

    def _get_credentials_dict(self):
        """获取凭证配置"""
        # 优先从 Streamlit Secrets 读取
        if hasattr(st, 'secrets') and 'gsc_credentials' in st.secrets:
            creds_dict = {
                "installed": {
                    "client_id": st.secrets["gsc_credentials"]["installed_client_id"],
                    "project_id": st.secrets["gsc_credentials"]["installed_project_id"],
                    "auth_uri": st.secrets["gsc_credentials"]["installed_auth_uri"],
                    "token_uri": st.secrets["gsc_credentials"]["installed_token_uri"],
                    "auth_provider_x509_cert_url": st.secrets["gsc_credentials"]["installed_auth_provider_x509_cert_url"],
                    "client_secret": st.secrets["gsc_credentials"]["installed_client_secret"],
                    "redirect_uris": st.secrets["gsc_credentials"]["installed_redirect_uris"]
                }
            }
            return creds_dict
        
        # 否则从本地文件读取
        if os.path.exists('credentials.json'):
            with open('credentials.json', 'r') as f:
                return json.load(f)
        
        raise FileNotFoundError("找不到 credentials.json 文件，且未配置 Streamlit Secrets")

    def _authenticate(self):
        """处理 OAuth 认证流程"""
        creds = None
        token_file = 'token.json'

        # 检查是否已有保存的令牌
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)

        # 如果没有有效凭据，进行授权
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds_dict = self._get_credentials_dict()
                
                # 创建临时凭证文件
                temp_creds_file = 'temp_credentials.json'
                with open(temp_creds_file, 'w') as f:
                    json.dump(creds_dict, f)
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    temp_creds_file, SCOPES)
                creds = flow.run_local_server(port=0)
                
                # 删除临时文件
                if os.path.exists(temp_creds_file):
                    os.remove(temp_creds_file)

            # 保存凭据供下次使用
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)

        # 构建 API 服务
        self.service = build('searchconsole', 'v1', credentials=creds)

    def get_sites(self):
        """获取用户有权限访问的所有网站列表"""
        try:
            site_list = self.service.sites().list().execute()
            return [site['siteUrl'] for site in site_list.get('siteEntry', [])]
        except HttpError as error:
            print(f'获取网站列表时出错: {error}')
            return []

    def query_data(self, site_url, start_date, end_date, dimensions=['query'],
                   row_limit=1000, device_type=None, country=None):
        """查询 Search Console 数据"""
        try:
            request = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': dimensions,
                'rowLimit': row_limit
            }

            # 添加过滤条件
            dimension_filters = []
            if device_type:
                dimension_filters.append({
                    'dimension': 'device',
                    'operator': 'equals',
                    'expression': device_type
                })
            if country:
                dimension_filters.append({
                    'dimension': 'country',
                    'operator': 'equals',
                    'expression': country
                })

            if dimension_filters:
                request['dimensionFilterGroups'] = [{
                    'filters': dimension_filters
                }]

            response = self.service.searchanalytics().query(
                siteUrl=site_url, body=request).execute()

            # 转换为 DataFrame
            if 'rows' not in response:
                return pd.DataFrame()

            rows = response['rows']
            data = []
            for row in rows:
                item = {}
                for i, dim in enumerate(dimensions):
                    item[dim] = row['keys'][i]
                item['clicks'] = row['clicks']
                item['impressions'] = row['impressions']
                item['ctr'] = row['ctr']
                item['position'] = row['position']
                data.append(item)

            df = pd.DataFrame(data)
            return df

        except HttpError as error:
            print(f'查询数据时出错: {error}')
            return pd.DataFrame()

    def get_keyword_data(self, site_url, days=30, row_limit=1000,
                        device_type=None, country=None):
        """获取关键词数据"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        return self.query_data(
            site_url=site_url,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            dimensions=['query'],
            row_limit=row_limit,
            device_type=device_type,
            country=country
        )

    def get_keyword_trend(self, site_url, keyword, days=90):
        """获取特定关键词的趋势数据"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        try:
            request = {
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d'),
                'dimensions': ['date'],
                'dimensionFilterGroups': [{
                    'filters': [{
                        'dimension': 'query',
                        'operator': 'equals',
                        'expression': keyword
                    }]
                }]
            }

            response = self.service.searchanalytics().query(
                siteUrl=site_url, body=request).execute()

            if 'rows' not in response:
                return pd.DataFrame()

            rows = response['rows']
            data = []
            for row in rows:
                data.append({
                    'date': row['keys'][0],
                    'clicks': row['clicks'],
                    'impressions': row['impressions'],
                    'ctr': row['ctr'],
                    'position': row['position']
                })

            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date')
            return df

        except HttpError as error:
            print(f'查询趋势数据时出错: {error}')
            return pd.DataFrame()
