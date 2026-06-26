import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import re
import numpy as np
from datetime import datetime

st.set_page_config(page_title="廣告組合成效分析平台", layout="wide", initial_sidebar_state="expanded")

# ===== CONSTANTS =====
COLUMN_MAP = {
    '廣告組合名稱': 'name',
    '廣告組合投遞': 'delivery_status',
    '廣告組合預算': 'budget',
    '廣告組合預算類型': 'budget_type',
    '花費金額 (TWD)': 'spend',
    '觸及人數': 'reach',
    '曝光次數': 'impressions',
    '頻率': 'frequency',
    'CTR（全部）': 'ctr',
    'CPM（每千次廣告曝光成本） (TWD)': 'cpm',
    'CPC（全部） (TWD)': 'cpc',
    '連結點擊次數': 'link_clicks',
    '不重複連結點擊人數': 'unique_link_clicks',
    '內容瀏覽次數': 'content_views',
    '加到購物車次數': 'add_to_cart',
    '開始結帳次數': 'checkouts',
    '購買次數': 'purchases',
    '每次購買成本 (TWD)': 'cpa',
    '購買 ROAS（廣告投資報酬率）': 'roas',
    '建立日期': 'created_date',
    '最後編輯日期': 'last_edited_date',
    '貼文互動次數': 'post_engagement',
    'ThruPlay 次數': 'thruplay',
    '影片播放 3 秒以上的次數': 'video_3s_views',
}
REQUIRED_COLUMNS = ['廣告組合名稱', '花費金額 (TWD)']
REVENUE_FIELD_CANDIDATES = ['購買轉換值', '平均購買轉換值']

# ===== HELPER FUNCTIONS =====
def excelDateToStr(v):
    if v is None or v == '':
        return None
    if isinstance(v, (int, float)):
        try:
            d = pd.Timestamp(v, unit='D', origin='1900-01-01')
            return d.strftime('%Y-%m-%d')
        except:
            return None
    try:
        d = pd.to_datetime(v)
        return d.strftime('%Y-%m-%d')
    except:
        return str(v)

def parseAdSetName(rawName):
    n = str(rawName)
    parts = [p.strip() for p in re.split(r'\s*-\s*', n) if p.strip()]
    dateTag = None
    if parts and re.match(r'^\d{4}$', parts[-1]):
        dateTag = parts[-1]
        parts = parts[:-1]
    if len(parts) > 3 and re.match(r'^\d{4}$', parts[-1]):
        parts = parts[:-1]
    deliveryType = parts[0] if len(parts) > 0 else None
    interest = parts[1] if len(parts) > 1 else None
    group = None
    extra = []
    for p in parts[2:]:
        if re.match(r'^KOL', p, re.I) or p in ('B組', 'A組'):
            group = p
        else:
            extra.append(p)
    if group is None and extra:
        group = ' - '.join(extra)
    if group is None:
        group = '未分類'
    return {'deliveryType': deliveryType, 'interest': interest or '未指定', 'group': group, 'dateTag': dateTag}

def numOrNull(v):
    if v is None or v == '' or v == '-':
        return None
    try:
        n = float(v)
        return n if not np.isnan(n) else None
    except:
        return None

def numOrZero(v):
    n = numOrNull(v)
    return n if n is not None else 0

def validateColumns(headerRow):
    missing = [c for c in REQUIRED_COLUMNS if c not in headerRow]
    return missing

def processWorkbook(df):
    headerRow = df.columns.tolist()
    missing = validateColumns(headerRow)
    if missing:
        raise ValueError(f"缺少必要欄位：{', '.join(missing)}")
    
    active = df[df['花費金額 (TWD)'] > 0].copy()
    if len(active) == 0:
        raise ValueError("找不到任何有花費金額的廣告組合")
    
    # 判斷收入欄位
    revenueField, revenueMode = None, None
    if '購買轉換值' in headerRow:
        revenueField, revenueMode = '購買轉換值', 'total'
    elif '平均購買轉換值' in headerRow:
        revenueField, revenueMode = '平均購買轉換值', 'avg'
    
    cleaned = []
    for _, row in active.iterrows():
        rec = {'name': row['廣告組合名稱']}
        for src, dst in COLUMN_MAP.items():
            if dst != 'name' and src in headerRow:
                rec[dst] = row[src]
        
        parsed = parseAdSetName(row['廣告組合名稱'])
        rec['campaign'] = parsed['group']
        rec['interest'] = parsed['interest']
        
        rec['spend'] = numOrZero(rec.get('spend'))
        for key in ['reach', 'impressions', 'link_clicks', 'unique_link_clicks', 'content_views', 
                    'add_to_cart', 'checkouts', 'purchases', 'post_engagement', 'thruplay', 'video_3s_views']:
            rec[key] = numOrZero(rec.get(key))
        
        for key in ['frequency', 'ctr', 'cpm']:
            rec[key] = numOrZero(rec.get(key)) or 0
        
        for key in ['cpc', 'cpa', 'roas']:
            rec[key] = numOrNull(rec.get(key))
        
        purchaseValue = None
        if revenueMode == 'total':
            purchaseValue = numOrNull(row.get(revenueField))
        elif revenueMode == 'avg':
            avgVal = numOrNull(row.get(revenueField))
            purchaseValue = (avgVal * rec['purchases']) if (avgVal and rec['purchases'] > 0) else None
        
        if purchaseValue is None and rec.get('roas') and rec['spend'] > 0:
            purchaseValue = rec['spend'] * rec['roas']
        
        rec['purchase_value'] = purchaseValue
        if rec.get('roas') is None and purchaseValue and rec['spend'] > 0:
            rec['roas'] = purchaseValue / rec['spend']
        
        if rec.get('cpa') is None and rec['purchases'] > 0:
            rec['cpa'] = rec['spend'] / rec['purchases']
        
        rec['created_date'] = excelDateToStr(rec.get('created_date'))
        rec['last_edited_date'] = excelDateToStr(rec.get('last_edited_date'))
        rec['budget'] = numOrZero(rec.get('budget'))
        rec['delivery_status'] = rec.get('delivery_status') or 'unknown'
        
        cleaned.append(rec)
    
    return cleaned

# ===== LAYOUT =====
st.markdown("# 廣告組合成效分析平台")
st.markdown("**線上互動版** — 上傳 Meta 廣告組合報表 Excel，自動分析 CPA 與每日留存組數")

col1, col2 = st.columns([3, 1])
with col2:
    st.markdown("---")
    if st.button("🔄 重新上傳", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# ===== FILE UPLOAD =====
uploaded_file = st.file_uploader("上傳廣告組合報表（.xlsx）", type=['xlsx'])

if not uploaded_file:
    st.info("📁 請選擇檔案。支援 Meta 廣告管理工具匯出的「廣告組合」層級報表。")
    st.stop()

# Parse file
try:
    df = pd.read_excel(uploaded_file, sheet_name=0)
    DATA = processWorkbook(df)
    st.session_state.data_loaded = True
except Exception as e:
    st.error(f"❌ 解析失敗：{str(e)}")
    st.stop()

# ===== ANALYTICS =====
total_spend = sum(d['spend'] for d in DATA)
total_purchases = sum(d['purchases'] for d in DATA)
overall_cpa = (total_spend / total_purchases) if total_purchases > 0 else None
total_impressions = sum(d['impressions'] for d in DATA)
active_count = sum(1 for d in DATA if d['delivery_status'] == 'active')
unique_days = len(set(d['created_date'] for d in DATA if d.get('created_date')))
avg_daily_groups = len(DATA) / unique_days if unique_days > 0 else 0

# ===== KPI ROW =====
col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    st.metric("整體 CPA", f"${overall_cpa:.0f}" if overall_cpa else "—")
with col2:
    st.metric("平均每日留存組數", f"{avg_daily_groups:.1f} 組/天")
with col3:
    st.metric("總花費 (TWD)", f"${total_spend:,.0f}")
with col4:
    st.metric("總購買次數", f"{int(total_purchases)}")
with col5:
    st.metric("總曝光次數", f"{total_impressions:,.0f}")
with col6:
    st.metric("進行中組合數", f"{active_count}/{len(DATA)}")

st.markdown("---")

# ===== TABS =====
tab1, tab2, tab3 = st.tabs(["📊 廣告組合明細", "🎯 分類比較", "📈 CPA 與留存組數趨勢"])

# ===== TAB 1: TABLE =====
with tab1:
    col_campaign, col_status, col_search, col_purchase, col_reset = st.columns(5)
    with col_campaign:
        campaigns = sorted(set(d['campaign'] for d in DATA))
        selected_campaign = st.selectbox("分類/組別", ["全部"] + campaigns)
    with col_status:
        selected_status = st.selectbox("投遞狀態", ["全部", "active", "inactive", "scheduled"])
    with col_search:
        search_text = st.text_input("搜尋興趣/名稱")
    with col_purchase:
        has_purchase = st.selectbox("購買轉換", ["全部", "有購買", "無購買"])
    with col_reset:
        st.write("")  # spacing

    # Filter
    filtered = DATA
    if selected_campaign != "全部":
        filtered = [d for d in filtered if d['campaign'] == selected_campaign]
    if selected_status != "全部":
        filtered = [d for d in filtered if d['delivery_status'] == selected_status]
    if search_text:
        search_lower = search_text.lower()
        filtered = [d for d in filtered if search_lower in (d.get('name','') + d.get('interest','') + d.get('campaign','')).lower()]
    if has_purchase == "有購買":
        filtered = [d for d in filtered if d['purchases'] > 0]
    elif has_purchase == "無購買":
        filtered = [d for d in filtered if d['purchases'] == 0]
    
    st.caption(f"顯示 {len(filtered)} / {len(DATA)} 筆")
    
    # Display table
    display_cols = ['campaign', 'interest', 'delivery_status', 'cpa', 'purchases', 'spend', 'impressions', 'ctr', 'cpm', 'roas', 'created_date']
    df_display = pd.DataFrame([{
        '分類': d['campaign'],
        '興趣': d['interest'],
        '狀態': d['delivery_status'],
        'CPA': f"${d['cpa']:.0f}" if d.get('cpa') else "—",
        '購買': f"{int(d['purchases'])}",
        '花費': f"${d['spend']:,.0f}",
        '曝光': f"{d['impressions']:,.0f}",
        'CTR': f"{d['ctr']:.2f}%",
        'CPM': f"${d['cpm']:.0f}",
        'ROAS': f"{d['roas']:.2f}x" if d.get('roas') else "—",
        '建立日期': d.get('created_date', '—')
    } for d in filtered])
    
    st.dataframe(df_display, use_container_width=True, height=500)

# ===== TAB 2: CAMPAIGN COMPARISON =====
with tab2:
    # Aggregate by campaign
    agg_map = {}
    for d in DATA:
        c = d['campaign']
        if c not in agg_map:
            agg_map[c] = {'campaign': c, 'spend': 0, 'purchases': 0, 'purchase_value': 0, 'count': 0, 'reach': 0, 'impressions': 0, 'ctr_sum': 0}
        agg_map[c]['spend'] += d['spend']
        agg_map[c]['purchases'] += d['purchases']
        agg_map[c]['purchase_value'] += d.get('purchase_value') or 0
        agg_map[c]['count'] += 1
        agg_map[c]['reach'] += d['reach']
        agg_map[c]['impressions'] += d['impressions']
        agg_map[c]['ctr_sum'] += d['ctr']
    
    agg_list = []
    for c in agg_map.values():
        c['cpa'] = c['spend'] / c['purchases'] if c['purchases'] > 0 else None
        c['roas'] = c['purchase_value'] / c['spend'] if c['spend'] > 0 and c['purchase_value'] > 0 else None
        c['ctr'] = c['ctr_sum'] / c['count'] if c['count'] > 0 else 0
        agg_list.append(c)
    
    sort_by = st.selectbox("排序依據", ["CPA（低到高）", "花費", "購買次數", "ROAS"])
    if sort_by == "CPA（低到高）":
        agg_list.sort(key=lambda x: x['cpa'] if x['cpa'] else float('inf'))
    elif sort_by == "花費":
        agg_list.sort(key=lambda x: x['spend'], reverse=True)
    elif sort_by == "購買次數":
        agg_list.sort(key=lambda x: x['purchases'], reverse=True)
    else:
        agg_list.sort(key=lambda x: x['roas'] if x['roas'] else 0, reverse=True)
    
    # Display cards
    cols = st.columns(2)
    for idx, agg in enumerate(agg_list):
        with cols[idx % 2]:
            with st.container(border=True):
                st.subheader(agg['campaign'])
                st.caption(f"{agg['count']} 個廣告組合")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("CPA", f"${agg['cpa']:.0f}" if agg['cpa'] else "—")
                    st.metric("購買", f"{int(agg['purchases'])}")
                    st.metric("ROAS", f"{agg['roas']:.2f}x" if agg['roas'] else "—")
                with col2:
                    st.metric("花費", f"${agg['spend']:,.0f}")
                    st.metric("觸及", f"{agg['reach']:,.0f}")
                    st.metric("CTR", f"{agg['ctr']:.2f}%")

# ===== TAB 3: TRENDS =====
with tab3:
    # Aggregate by date
    date_map = {}
    for d in DATA:
        date = d.get('created_date') or '未知'
        if date not in date_map:
            date_map[date] = {'date': date, 'spend': 0, 'purchases': 0, 'purchase_value': 0, 'impressions': 0, 'ctr_sum': 0, 'count': 0}
        date_map[date]['spend'] += d['spend']
        date_map[date]['purchases'] += d['purchases']
        date_map[date]['purchase_value'] += d.get('purchase_value') or 0
        date_map[date]['impressions'] += d['impressions']
        date_map[date]['ctr_sum'] += d['ctr']
        date_map[date]['count'] += 1
    
    date_list = sorted([{
        'date': v['date'],
        'groups': v['count'],
        'spend': v['spend'],
        'purchases': v['purchases'],
        'cpa': v['spend'] / v['purchases'] if v['purchases'] > 0 else None,
        'impressions': v['impressions'],
        'ctr': v['ctr_sum'] / v['count'] if v['count'] > 0 else 0,
    } for v in date_map.values()], key=lambda x: x['date'])
    
    df_date = pd.DataFrame(date_list)
    
    # Retention & CPA chart
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=df_date['date'], y=df_date['groups'], name='留存組數', marker_color='#F0C76B', yaxis='y'), secondary_y=False)
    fig.add_trace(go.Scatter(x=df_date['date'], y=df_date['cpa'], name='CPA', line=dict(color='#FF8A5C', width=3), yaxis='y2'), secondary_y=True)
    fig.update_layout(hovermode='x unified', height=400, title="每日留存組數 vs CPA")
    fig.update_yaxes(title_text="廣告組合數", secondary_y=False)
    fig.update_yaxes(title_text="CPA (TWD)", secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)
    
    # Spend by campaign pie
    agg_map_pie = {}
    for d in DATA:
        c = d['campaign']
        if c not in agg_map_pie:
            agg_map_pie[c] = 0
        agg_map_pie[c] += d['spend']
    
    df_pie = pd.DataFrame([{'campaign': k, 'spend': v} for k, v in sorted(agg_map_pie.items(), key=lambda x: x[1], reverse=True)])
    fig_pie = px.pie(df_pie, values='spend', names='campaign', title='各分類花費佔比', height=400)
    st.plotly_chart(fig_pie, use_container_width=True)
    
    # Daily metrics
    metric_choice = st.selectbox("選擇指標", ["花費", "購買次數", "曝光次數", "CTR"])
    metric_key = {'花費': 'spend', '購買次數': 'purchases', '曝光次數': 'impressions', 'CTR': 'ctr'}[metric_choice]
    
    fig_line = px.line(df_date, x='date', y=metric_key, markers=True, title=f"每日 {metric_choice} 趨勢", height=400)
    st.plotly_chart(fig_line, use_container_width=True)

st.markdown("---")
st.caption("✅ 資料已成功載入。關閉此網頁或上傳新檔案時，資料將自動清除。")
