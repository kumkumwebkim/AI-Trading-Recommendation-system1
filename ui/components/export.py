# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import json
from io import StringIO
from datetime import datetime

def export_data_section(stock_data, ml_signal, backtest_metrics):
    """Render data export functionality"""
    st.markdown("""
        <div class="section-header" style="margin: 30px 0;">
            <div class="section-title">
                💾 Export Trading Data
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
            <div class="metric-box" style="background: linear-gradient(135deg, rgba(100, 150, 255, 0.1), rgba(80, 130, 255, 0.05)); border-color: rgba(100, 150, 255, 0.2); margin-bottom: 15px;">
                <div style="font-size: 40px; margin-bottom: 10px;">📊</div>
                <div style="font-size: 16px; font-weight: 600; color: white;">Price Data Export</div>
                <div style="font-size: 12px; color: rgba(255, 255, 255, 0.6); margin-top: 5px;">OHLC, Volume, Indicators</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Export Price Data as CSV
        if st.button("📥 Export Price Data", key="export_price", width="stretch"):
            df = pd.DataFrame({
                'Date': stock_data.dates,
                'Open': stock_data.opens,
                'High': stock_data.highs,
                'Low': stock_data.lows,
                'Close': stock_data.closes,
                'Volume': stock_data.volumes,
                'RSI': stock_data.rsi,
                'SMA_20': stock_data.sma_20,
                'SMA_50': stock_data.sma_50,
                'MACD': stock_data.macd,
                'MACD_Signal': stock_data.macd_signal
            })
            csv = df.to_csv(index=False)
            st.download_button(
                label="⬇️ Download CSV",
                data=csv,
                file_name=f"{stock_data.symbol}_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width="stretch"
            )
    
    with col2:
        st.markdown("""
            <div class="metric-box" style="background: linear-gradient(135deg, rgba(0, 255, 127, 0.1), rgba(0, 200, 100, 0.05)); border-color: rgba(0, 255, 127, 0.2); margin-bottom: 15px;">
                <div style="font-size: 40px; margin-bottom: 10px;">🤖</div>
                <div style="font-size: 16px; font-weight: 600; color: white;">AI Signal Export</div>
                <div style="font-size: 12px; color: rgba(255, 255, 255, 0.6); margin-top: 5px;">Action, Confidence, Reasoning</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Export ML Signal as JSON
        if st.button("📥 Export AI Signal", key="export_signal", width="stretch"):
            if ml_signal is None:
                st.warning("No AI Signal available. Generate one first on the AI Signals page.")
            else:
                signal_dict = {
                    "symbol": stock_data.symbol,
                    "action": ml_signal.action,
                    "confidence": ml_signal.confidence,
                    "timestamp": ml_signal.timestamp.isoformat(),
                    "reasoning": ml_signal.reasoning,
                    "key_factors": ml_signal.key_factors
                }
                json_str = json.dumps(signal_dict, indent=2)
                st.download_button(
                    label="⬇️ Download JSON",
                    data=json_str,
                    file_name=f"{stock_data.symbol}_signal_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                    width="stretch"
                )
    
    with col3:
        st.markdown("""
            <div class="metric-box" style="background: linear-gradient(135deg, rgba(255, 215, 0, 0.1), rgba(255, 200, 0, 0.05)); border-color: rgba(255, 215, 0, 0.2); margin-bottom: 15px;">
                <div style="font-size: 40px; margin-bottom: 10px;">🎯</div>
                <div style="font-size: 16px; font-weight: 600; color: white;">Backtest Export</div>
                <div style="font-size: 12px; color: rgba(255, 255, 255, 0.6); margin-top: 5px;">Metrics, Returns, Analysis</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Export Backtest Results
        if st.button("📥 Export Backtest", key="export_backtest", width="stretch"):
            def metrics_value(obj, attr, alias=None, default=0):
                try:
                    if isinstance(obj, dict):
                        if attr in obj:
                            return obj[attr]
                        if alias and alias in obj:
                            return obj[alias]
                    else:
                        if hasattr(obj, attr):
                            return getattr(obj, attr)
                        if alias and hasattr(obj, alias):
                            return getattr(obj, alias)
                except Exception:
                    pass
                return default

            src = backtest_metrics.ml_metrics if hasattr(backtest_metrics, "ml_metrics") else backtest_metrics
            backtest_dict = {
                "symbol": stock_data.symbol,
                "metrics": {
                    "total_trades": metrics_value(src, "total_trades"),
                    "win_rate": metrics_value(src, "win_rate_pct", "win_rate"),
                    "max_drawdown": metrics_value(src, "max_drawdown_pct", "max_drawdown"),
                    "total_return": metrics_value(src, "total_return_pct", "total_return"),
                    "sharpe_ratio": metrics_value(src, "sharpe_ratio")
                },
                "monthly_returns": getattr(backtest_metrics, "monthly_returns", None)
            }
            json_str = json.dumps(backtest_dict, indent=2)
            st.download_button(
                label="⬇️ Download JSON",
                data=json_str,
                file_name=f"{stock_data.symbol}_backtest_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json",
                width="stretch"
            )
