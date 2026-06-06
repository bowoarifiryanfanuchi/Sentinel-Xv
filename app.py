import streamlit as st
import pandas as pd
import io
import networkx as nx
from pyvis.network import Network
import tempfile
import os
import re
import plotly.express as px
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS
import streamlit.components.v1 as components
from llm import process_batch_with_llm
import concurrent.futures

st.set_page_config(page_title="Sentinel-X Dashboard", page_icon="🕵️", layout="wide")

# Inisialisasi Session State
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'result_df' not in st.session_state:
    st.session_state.result_df = None
if 'gexf_data' not in st.session_state:
    st.session_state.gexf_data = None
if 'html_net' not in st.session_state:
    st.session_state.html_net = None

def extract_username(text):
    """Mengekstrak username @ dari teks panjang"""
    text = str(text)
    match = re.search(r'(@[A-Za-z0-9_]+)', text)
    if match:
        return match.group(1)
    return text.split('|')[0].strip()

st.title("🛡️ Sentinel-X: Data Intelligence Dashboard (X Edition)")
st.markdown("Platform monitoring media sosial komprehensif.")

# 1. UPLOAD FILE
with st.sidebar:
    st.header("1. Input Data")
    uploaded_file = st.file_uploader("Upload Dataset X (CSV/Excel)", type=["csv", "xlsx"])
    
    if st.button("Kosongkan Data / Reset", type="secondary"):
        st.session_state.analysis_done = False
        st.session_state.result_df = None
        st.session_state.gexf_data = None
        st.session_state.html_net = None
        st.rerun()

if uploaded_file is not None and not st.session_state.analysis_done:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        st.success(f"File diunggah: {len(df)} baris.")
        with st.expander("Pratinjau Data"):
            st.dataframe(df.astype(str).head())
    except Exception as e:
        st.error(f"Gagal membaca file: {e}")
        st.stop()

    if st.button("🚀 Mulai Analisis Ekstensif", width='stretch', type="primary"):
        with st.spinner("Membersihkan data & memproses AI..."):
            if 'X akun' in df.columns:
                df['X akun_cleaned'] = df['X akun'].apply(extract_username)
            else:
                df['X akun_cleaned'] = "Unknown"

            for col in ['Komentar', 'Repost', 'Likes', 'Views']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                else:
                    df[col] = 0
            df.fillna("", inplace=True)
            if 'row_id' not in df.columns:
                df['row_id'] = range(1, len(df) + 1)
                
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            batch_size = 10
            total_rows = len(df)
            all_results = []
            
            # Mempersiapkan batasan batch
            batches = [df.iloc[i:min(i + batch_size, total_rows)] for i in range(0, total_rows, batch_size)]
            completed_rows = 0
            
            status_text.markdown(f"**Status:** Memulai analisis paralel untuk {total_rows} baris...")
            
            # PROSES BATCH SECARA PARALEL (Diturunkan menjadi 5 jalur agar OpenRouter & Groq tidak Rate Limit)
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # Mengirim semua batch ke AI secara bersamaan
                future_to_batch = {executor.submit(process_batch_with_llm, batch): batch for batch in batches}
                
                for future in concurrent.futures.as_completed(future_to_batch):
                    batch_df = future_to_batch[future]
                    try:
                        llm_results = future.result()
                        llm_dict = {str(item.get('row_id')): item for item in llm_results}
                        
                        for _, row in batch_df.iterrows():
                            row_id_str = str(row['row_id'])
                            res = llm_dict.get(row_id_str, {})
                            
                            row_data = row.to_dict()
                            row_data['Sentiment'] = res.get('primary_sentiment', 'Netral')
                            row_data['Emotion'] = res.get('emotion', 'Netral')
                            row_data['Narrative_Category'] = res.get('narrative_category', 'Tanpa Kategori')
                            row_data['Actor_Type'] = res.get('actor_type', 'Organik')
                            
                            attacked = res.get('attacked_entities', [])
                            defended = res.get('defended_entities', [])
                            hashtags = res.get('hashtags', [])
                            
                            row_data['Attacked_Entities'] = ", ".join(attacked) if isinstance(attacked, list) else ""
                            row_data['Defended_Entities'] = ", ".join(defended) if isinstance(defended, list) else ""
                            row_data['Hashtags_Extracted'] = ", ".join(hashtags) if isinstance(hashtags, list) else ""
                            
                            all_results.append(row_data)
                    except Exception as e:
                        st.error(f"Gagal memproses batch: {str(e)}")
                        # Teruskan eksekusi dengan data kosong agar ketahuan
                        pass
                    
                    completed_rows += len(batch_df)
                    progress_bar.progress(min(completed_rows / total_rows, 1.0))
                    status_text.markdown(f"**Status:** Selesai menganalisis {completed_rows} dari {total_rows} baris... ⚡(Mode Cepat)")
                
            # SNA GRAPH GENERATION
            status_text.markdown("**Status:** Membangun grafik jaringan (SNA)...")
            result_df = pd.DataFrame(all_results)
            
            G = nx.DiGraph()
            for _, row in result_df.iterrows():
                akun = str(row.get('X akun_cleaned', '')).strip()
                if not akun: continue
                
                views = row.get('Views', 0)
                likes = row.get('Likes', 0)
                node_weight = (0.6 * views) + (0.4 * likes)
                
                if not G.has_node(akun): G.add_node(akun, type="account", weight=0, title=akun, size=10)
                G.nodes[akun]['weight'] = G.nodes[akun].get('weight', 0) + node_weight
                G.nodes[akun]['size'] = min(50, 10 + (G.nodes[akun]['weight'] / 1000))
                
                attacked = [e.strip() for e in str(row.get('Attacked_Entities', '')).split(',') if e.strip()]
                defended = [e.strip() for e in str(row.get('Defended_Entities', '')).split(',') if e.strip()]
                
                for entity in attacked:
                    if not G.has_node(entity): G.add_node(entity, type="entity", weight=0, title=entity, size=15, color='red')
                    if G.has_edge(akun, entity): G[akun][entity]['weight'] += 1
                    else: G.add_edge(akun, entity, type="attacks", weight=1, color='red')
                        
                for entity in defended:
                    if not G.has_node(entity): G.add_node(entity, type="entity", weight=0, title=entity, size=15, color='green')
                    if G.has_edge(akun, entity): G[akun][entity]['weight'] += 1
                    else: G.add_edge(akun, entity, type="defends", weight=1, color='green')

            with tempfile.NamedTemporaryFile(delete=False, suffix=".gexf") as tmp:
                nx.write_gexf(G, tmp.name)
                gexf_path = tmp.name
                
            with open(gexf_path, "rb") as f:
                gexf_data = f.read()
            os.remove(gexf_path)
            
            # Create interactive HTML network
            net = Network(height="600px", width="100%", bgcolor="#222222", font_color="white", directed=True)
            net.from_nx(G)
            net.repulsion(node_distance=100, spring_length=200)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
                net.save_graph(tmp.name)
                html_net_path = tmp.name
            with open(html_net_path, 'r', encoding='utf-8') as f:
                html_net = f.read()
            os.remove(html_net_path)
            
            # SAVE TO STATE
            st.session_state.result_df = result_df
            st.session_state.gexf_data = gexf_data
            st.session_state.html_net = html_net
            st.session_state.analysis_done = True
            st.rerun()

# ----------------- RENDER DASHBOARD -----------------
if st.session_state.analysis_done and st.session_state.result_df is not None:
    df_res = st.session_state.result_df
    
    st.success("✨ Analisis Selesai! Berikut adalah Report Interaktif Anda.")
    
    # Pre-processing Datetime for Trends
    if 'Tanggal' in df_res.columns and 'Waktu' in df_res.columns:
        df_res['Datetime'] = pd.to_datetime(df_res['Tanggal'].astype(str) + ' ' + df_res['Waktu'].astype(str), errors='coerce')
    else:
        df_res['Datetime'] = pd.NaT
        
    with st.sidebar:
        st.header("2. Unduh Laporan")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_res.to_excel(writer, index=False, sheet_name='Data_Analisis')
        st.download_button("📊 Download Excel Report", buffer.getvalue(), "SentinelX_FullReport.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width='stretch')
        st.download_button("🕸️ Download Graph (.gexf)", st.session_state.gexf_data, "SentinelX_Network.gexf", "application/xml", width='stretch')

    t1, t2, t3, t4, t5, t6 = st.tabs(["📈 Volume & Trend", "🎭 Sentiment & Emotion", "👤 KOL & Aktor", "🗣️ Issue & Hashtag", "🕸️ Network (SNA)", "🔥 Top Post & Wordcloud"])
    
    with t1:
        st.subheader("1. Volume & Trend Analysis")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Post", f"{len(df_res):,}")
        col2.metric("Total Interaksi (Views)", f"{df_res['Views'].sum():,}")
        col3.metric("Total Interaksi (Likes)", f"{df_res['Likes'].sum():,}")
        col4.metric("Total Interaksi (Reposts)", f"{df_res['Repost'].sum():,}")
        
        if not df_res['Datetime'].isna().all():
            st.markdown("### Pergerakan Isu Berdasarkan Waktu (Peak Time)")
            trend_df = df_res.dropna(subset=['Datetime']).groupby(df_res['Datetime'].dt.floor('h')).size().reset_index(name='Jumlah')
            fig_trend = px.line(trend_df, x='Datetime', y='Jumlah', title="Volume Percakapan per Jam", markers=True)
            st.plotly_chart(fig_trend, width='stretch')
                
    with t2:
        st.subheader("2 & 3. Sentiment & Emotion Analysis")
        col1, col2 = st.columns(2)
        with col1:
            fig_sent = px.pie(df_res, names='Sentiment', title="Proporsi Sentimen Agregat", hole=0.4,
                              color='Sentiment', color_discrete_map={'Positif':'green','Negatif':'red','Netral':'gray'})
            st.plotly_chart(fig_sent, width='stretch')
        with col2:
            fig_emo = px.bar(df_res['Emotion'].value_counts().reset_index(), x='Emotion', y='count', title="Ekstraksi Emosi Dominan Audiens")
            st.plotly_chart(fig_emo, width='stretch')
            
        if not df_res['Datetime'].isna().all():
            st.markdown("### Perbandingan Rasio Sentimen Antar Waktu")
            sent_time_df = df_res.dropna(subset=['Datetime']).groupby([df_res['Datetime'].dt.floor('h'), 'Sentiment']).size().reset_index(name='Jumlah')
            fig_sent_time = px.bar(sent_time_df, x='Datetime', y='Jumlah', color='Sentiment', title="Sentimen Berdasarkan Waktu", barmode='stack', color_discrete_map={'Positif':'green','Negatif':'red','Netral':'gray'})
            st.plotly_chart(fig_sent_time, width='stretch')

    with t3:
        st.subheader("6. KOL & Aktor Analysis")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Identifikasi Organik vs Buzzer")
            fig_actor = px.pie(df_res, names='Actor_Type', title="Proporsi Aktor (Organik vs Terkoordinasi)", hole=0.4)
            st.plotly_chart(fig_actor, width='stretch')
        with col2:
            st.markdown("### Top Influencers (Hubs)")
            influencer_df = df_res.groupby('X akun_cleaned')['Views'].sum().sort_values(ascending=False).head(10).reset_index()
            fig_inf = px.bar(influencer_df, x='Views', y='X akun_cleaned', orientation='h', title="Top 10 Akun Penggerak Utama by Views")
            fig_inf.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_inf, width='stretch')

    with t4:
        st.subheader("7 & 10. Issue & Hashtag Analysis")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Peta Perdebatan Sub-Isu Pokok")
            nar_df = df_res['Narrative_Category'].value_counts().reset_index().head(10)
            fig_nar = px.bar(nar_df, x='count', y='Narrative_Category', orientation='h', title="Top 10 Narasi Utama")
            fig_nar.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_nar, width='stretch')
        with col2:
            st.markdown("### Pemetaan Tagar Utama")
            all_hashtags = []
            for tags in df_res['Hashtags_Extracted'].dropna():
                all_hashtags.extend([t.strip().lower() for t in tags.split(',') if t.strip()])
            if all_hashtags:
                tag_df = pd.Series(all_hashtags).value_counts().reset_index().head(10)
                tag_df.columns = ['Hashtag', 'Jumlah']
                fig_tag = px.bar(tag_df, x='Jumlah', y='Hashtag', orientation='h', title="Top 10 Hashtag Penggerak Kampanye")
                fig_tag.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_tag, width='stretch')
            else:
                st.info("Tidak ada hashtag yang terdeteksi.")

    with t5:
        st.subheader("5. Social Network Analysis (SNA)")
        st.markdown("Peta jaringan interaksi dan polarisasi kubu (Pro vs Kontra). Node merah = Diserang, Node hijau = Dibela.")
        if st.session_state.html_net:
            components.html(st.session_state.html_net, height=600)
        else:
            st.warning("Grafik interaktif gagal dimuat. Anda masih bisa mengunduh file .gexf di menu samping.")

    with t6:
        st.subheader("8 & 9. Top Post & Wordcloud")
        col1, col2 = st.columns([1.5, 1])
        with col1:
            st.markdown("### Katalog Konten Tertinggi (Engagement)")
            top_posts = df_res.sort_values(by='Views', ascending=False).head(5)[['X akun_cleaned', 'Views', 'Likes', 'Konten']]
            for _, r in top_posts.iterrows():
                st.info(f"**👤 {r['X akun_cleaned']}** | 👀 {r['Views']} Views | ❤️ {r['Likes']} Likes\n\n{r['Konten']}")
        with col2:
            st.markdown("### Leksikon (Top Words)")
            text_konten = " ".join(df_res['Konten'].dropna().astype(str))
            
            # Cleaning text untuk Wordcloud (hapus link, mention, dll)
            text_konten = re.sub(r'http\S+', '', text_konten)
            text_konten = re.sub(r'@\w+', '', text_konten)
            
            # Daftar Stopwords Bahasa Indonesia Tambahan (Kata hubung & slang)
            indo_stopwords = set([
                "yang", "di", "ke", "dari", "dan", "atau", "untuk", "pada", "dengan",
                "ini", "itu", "juga", "sudah", "akan", "dalam", "bisa", "ada", "tidak",
                "ya", "yg", "buat", "gak", "kalo", "aku", "saya", "kamu", "dia", 
                "mereka", "kita", "kami", "sih", "aja", "dong", "deh", "kok", "kan", 
                "udah", "belum", "nya", "dari", "lagi", "terus", "biar", "kalau", 
                "sama", "tapi", "banyak", "lebih", "paling", "banget", "mah", "pun"
            ])
            custom_stopwords = STOPWORDS.union(indo_stopwords)

            if text_konten.strip():
                try:
                    wordcloud = WordCloud(
                        width=600, height=600, 
                        background_color='white', 
                        max_words=100,
                        stopwords=custom_stopwords,
                        collocations=False
                    ).generate(text_konten)
                    fig, ax = plt.subplots()
                    ax.imshow(wordcloud, interpolation='bilinear')
                    ax.axis("off")
                    st.pyplot(fig)
                except:
                    st.info("Teks terlalu sedikit untuk wordcloud.")
