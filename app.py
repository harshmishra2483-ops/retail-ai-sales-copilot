
import os
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

import database as db
import ai_engine as ai
import market_intel

st.set_page_config(page_title="Retail AI Sales Copilot", layout="wide")

db.init_db()

st.title("Retail AI Sales Copilot")
st.caption(
    "Local working prototype • Synthetic/demo data by default • AI recommends, human decides."
)

# ---------- helpers ----------
def safe_int(v, default=0):
    try:
        return int(float(v))
    except Exception:
        return default

def outlet_options():
    return db.list_outlets()

def product_catalog():
    return db.list_products()

def current_mode():
    return "LIVE LLM" if ai.ANTHROPIC_API_KEY else "LOCAL FALLBACK"

with st.sidebar:
    st.header("System")
    st.success(f"AI mode: {current_mode()}")
    st.write("Database:", db.DB_PATH)
    st.write("Today:", date.today().isoformat())
    st.divider()
    st.caption("No automatic business action is sent. Human review is mandatory.")

tabs = st.tabs([
    "1. Visit & AI",
    "2. Retailer Orders",
    "3. Issues & History",
    "4. Area Executive",
    "5. Analytics",
    "6. Data Import",
    "7. Market Intelligence",
    "8. Voice / Video",
])

# ---------- TAB 1 ----------
with tabs[0]:
    st.subheader("Field visit capture")

    outlets = outlet_options()
    if not outlets:
        st.warning("No outlets loaded. Import your Excel file from the Data Import tab.")
    else:
        labels = {
            f"{o.get('outlet_name','Outlet')} | {o.get('area','')} | {o.get('outlet_id')}": o["outlet_id"]
            for o in outlets
        }

        c1, c2, c3 = st.columns(3)
        with c1:
            label = st.selectbox("Outlet", list(labels.keys()))
            outlet_id = labels[label]
        with c2:
            ds_name = st.text_input(
                "DS / Field Executive",
                value=db.get_outlet(outlet_id).get("ds_name", "") if db.get_outlet(outlet_id) else "",
            )
        with c3:
            ds_status = st.selectbox("Visit status", ["Visited", "Not visited", "Could not visit"])

        outlet = db.get_outlet(outlet_id) or {}

        st.markdown("### Stock by product")
        products = product_catalog()
        if products:
            stock_rows = []
            for p in products:
                pc1, pc2 = st.columns([3, 1])
                with pc1:
                    st.write(p["product_name"])
                with pc2:
                    qty = st.number_input(
                        f"Available | {p['product_name']}",
                        min_value=0,
                        value=safe_int(p.get("demo_stock", 0)),
                        step=1,
                        key=f"stock_{p['product_id']}",
                        label_visibility="collapsed",
                    )
                stock_rows.append((p["product_id"], p["product_name"], qty))
        else:
            st.info("No product catalog loaded yet. Add products through Excel import or the Data Import tab.")
            stock_rows = []

        st.markdown("### Retailer feedback")
        feedback = st.text_area(
            "Hindi / Hinglish / English",
            placeholder="Example: Marlboro nahi, current product ka stock khatam hai aur retailer ko 20 packs chahiye.",
            height=120,
        )

        vc1, vc2 = st.columns(2)
        with vc1:
            visit_photo = st.file_uploader(
                "DS visit proof photo (optional but recommended)",
                type=["jpg", "jpeg", "png"],
                key="visit_photo",
            )
        with vc2:
            retailer_media = st.file_uploader(
                "Retailer audio/video evidence (optional)",
                type=["wav", "mp3", "m4a", "mp4", "mov", "webm"],
                key="retailer_media",
            )

        lc1, lc2 = st.columns(2)
        with lc1:
            latitude = st.text_input("Latitude (optional)")
        with lc2:
            longitude = st.text_input("Longitude (optional)")

        st.markdown("### Retailer stock request")
        order_rows = []
        if products:
            selected_products = st.multiselect(
                "Products retailer wants to order",
                [p["product_name"] for p in products],
            )
            for pname in selected_products:
                p = next(x for x in products if x["product_name"] == pname)
                qty = st.number_input(
                    f"Required quantity — {pname}",
                    min_value=1,
                    value=1,
                    step=1,
                    key=f"order_{p['product_id']}",
                )
                order_rows.append((p["product_id"], pname, qty))

        if st.button("Analyze with AI", type="primary"):
            if not feedback.strip():
                st.error("Enter retailer feedback first.")
            else:
                with st.spinner("Analyzing feedback, product signals, history and opportunity..."):
                    result = ai.analyze_visit(
                        outlet_id=outlet_id,
                        feedback=feedback,
                        stock_rows=stock_rows,
                        order_rows=order_rows,
                    )
                st.session_state["last_analysis"] = result
                st.session_state["last_visit"] = {
                    "outlet_id": outlet_id,
                    "ds_name": ds_name,
                    "ds_status": ds_status,
                    "feedback": feedback,
                    "stock_rows": stock_rows,
                    "order_rows": order_rows,
                    "latitude": latitude,
                    "longitude": longitude,
                    "photo": visit_photo,
                    "media": retailer_media,
                }

        if "last_analysis" in st.session_state:
            r = st.session_state["last_analysis"]
            st.divider()
            st.subheader("AI Analysis — draft")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Issue", r.get("category", "-"))
            m2.metric("Priority", r.get("priority", "-"))
            m3.metric("Opportunity", r.get("opportunity_score", 0))
            m4.metric("AI confidence", r.get("ai_confidence", "-"))

            st.write("**Summary:**", r.get("summary", "-"))
            st.write("**Recommended action:**", r.get("recommended_action", "-"))
            st.write("**Sales opportunity:**", r.get("opportunity_reason", "-"))

            if r.get("recurrence_detected"):
                st.info(r.get("similar_context", "Related history found."))
            else:
                st.caption("History check: no same-category recurrence found.")

            if r.get("stock_alerts"):
                st.warning("Stock alerts: " + "; ".join(r["stock_alerts"]))

            if r.get("next_best_actions"):
                st.markdown("**Next-best actions:**")
                for a in r["next_best_actions"]:
                    st.write("•", a)

            st.divider()
            st.subheader("Human-in-the-loop decision")
            decision = st.radio(
                "Decision",
                ["Approve", "Edit", "Reject", "Escalate for manual review"],
                horizontal=True,
            )
            final_action = st.text_area(
                "Final approved action",
                value=r.get("recommended_action", ""),
            )
            owner = st.text_input(
                "Assigned owner",
                value=r.get("responsible_function", "Area Executive"),
            )

            if st.button("Save visit + human decision"):
                v = st.session_state["last_visit"]

                photo_path = ""
                if v.get("photo"):
                    photo_dir = Path("data/visit_photos")
                    photo_dir.mkdir(parents=True, exist_ok=True)
                    photo_path = str(photo_dir / f"{db.new_id('PHOTO')}_{v['photo'].name}")
                    with open(photo_path, "wb") as f:
                        f.write(v["photo"].getbuffer())

                visit_id = db.insert_visit({
                    "outlet_id": v["outlet_id"],
                    "visit_date": date.today().isoformat(),
                    "ds_name": v["ds_name"],
                    "ds_status": v["ds_status"],
                    "feedback": v["feedback"],
                    "latitude": v["latitude"],
                    "longitude": v["longitude"],
                    "photo_path": photo_path,
                    "ai_summary": r.get("summary", ""),
                    "ai_category": r.get("category", ""),
                    "ai_priority": r.get("priority", ""),
                    "ai_opportunity_score": r.get("opportunity_score", 0),
                })

                for product_id, pname, qty in v["stock_rows"]:
                    db.save_stock_snapshot(v["outlet_id"], visit_id, product_id, qty)

                issue_id = db.insert_issue({
                    "outlet_id": v["outlet_id"],
                    "visit_date": date.today().isoformat(),
                    "raw_feedback": v["feedback"],
                    "category": r.get("category", "Other"),
                    "sub_category": r.get("sub_category", "General"),
                    "product_service": r.get("product_service", ""),
                    "severity": r.get("severity", "Low"),
                    "priority": r.get("priority", "P3"),
                    "sentiment": r.get("sentiment", ""),
                    "summary": r.get("summary", ""),
                    "recommended_action": r.get("recommended_action", ""),
                    "responsible_function": r.get("responsible_function", "Area Executive"),
                    "similar_past_issue_ids": r.get("similar_past_issue_ids", ""),
                    "ai_confidence": r.get("ai_confidence", ""),
                    "human_decision": decision,
                    "final_action": final_action,
                    "status": "Closed - rejected" if decision == "Reject" else "Open",
                    "assigned_owner": owner,
                    "follow_up_date": (date.today() + timedelta(days=7)).isoformat(),
                })

                db.save_knowledge_feedback(
                    v["outlet_id"],
                    v["feedback"],
                    r.get("category", "Other"),
                    r.get("priority", "P3"),
                    r.get("opportunity_score", 0),
                    decision,
                )

                st.success(f"Visit {visit_id} and issue {issue_id} saved to history.")
                st.session_state.pop("last_analysis", None)
                st.session_state.pop("last_visit", None)

# ---------- TAB 2 ----------
with tabs[1]:
    st.subheader("Retailer Orders")
    st.caption(
        "Standalone retailer demand capture. Orders are linked to the outlet and routed "
        "to the responsible DS for execution."
    )

    outlets_for_orders = db.list_outlets()
    products_for_orders = db.list_products()

    if not outlets_for_orders:
        st.warning("No outlets are loaded.")
    elif not products_for_orders:
        st.warning("No products are loaded.")
    else:
        outlet_labels = {
            o["outlet_id"]: f'{o["outlet_name"]} | {o["area"]} | {o["outlet_id"]}'
            for o in outlets_for_orders
        }

        selected_outlet_id = st.selectbox(
            "Retailer / Outlet",
            list(outlet_labels.keys()),
            format_func=lambda x: outlet_labels[x],
            key="retailer_order_outlet",
        )

        selected_outlet = db.get_outlet(selected_outlet_id) or {}
        ds_name = selected_outlet.get("ds_name", "").strip()
        area = selected_outlet.get("area", "").strip()
        ae_name = selected_outlet.get("area_executive", "").strip()

        c1, c2, c3 = st.columns(3)
        c1.metric("Area", area or "Not mapped")
        c2.metric("Assigned DS", ds_name or "Not assigned")
        c3.metric("Area Executive", ae_name or "Not assigned")

        st.markdown("### New retailer order")

        selected_products = st.multiselect(
            "Select products",
            [p["product_name"] for p in products_for_orders],
            key="retailer_order_products",
        )

        order_rows = []

        if selected_products:
            for pname in selected_products:
                p = next(
                    x for x in products_for_orders
                    if x["product_name"] == pname
                )

                qty = st.number_input(
                    f"Quantity ? {pname}",
                    min_value=1,
                    value=1,
                    step=1,
                    key=f"retailer_qty_{p['product_id']}",
                )

                order_rows.append(
                    (p["product_id"], pname, int(qty))
                )

        if order_rows:
            st.markdown("### Order summary")
            for _, pname, qty in order_rows:
                st.write(f"? **{pname}** ? **{qty}**")

            if not ds_name:
                st.warning(
                    "This outlet has no DS mapped yet. Map the DS before submitting "
                    "the order so routing remains accountable."
                )

            if st.button(
                "Submit Retailer Order",
                type="primary",
                use_container_width=True,
                key="submit_retailer_order",
            ):
                try:
                    duplicate_order_id = db.has_recent_duplicate_order(
                        outlet_id=selected_outlet_id,
                        ds_name=ds_name,
                        order_rows=order_rows,
                        window_minutes=10,
                    )

                    if duplicate_order_id:
                        st.warning(
                            f"Duplicate order blocked. "
                            f"Same order was already submitted as {duplicate_order_id} "
                            f"within the last 10 minutes."
                        )
                    else:
                        # AI order intelligence: reuse the existing AI engine.
                        # The order is analyzed before AE review; AI does not auto-approve.
                        order_feedback = "Retailer order request: " + "; ".join(
                            f"{pname} x {qty}" for _, pname, qty in order_rows
                        )

                        latest_stock = db.get_latest_stock(selected_outlet_id)
                        order_stock_rows = [
                            (row["product_id"], row.get("product_name") or "Unknown product", row["quantity"])
                            for row in latest_stock
                        ]

                        with st.spinner("AI is evaluating order priority and outlet signals..."):
                            order_ai = ai.analyze_visit(
                                outlet_id=selected_outlet_id,
                                feedback=order_feedback,
                                stock_rows=order_stock_rows,
                                order_rows=order_rows,
                            )

                        ai_priority = str(order_ai.get("priority", "P3")).strip().upper()
                        priority_map = {
                            "P1": "Critical",
                            "P2": "High",
                            "P3": "Normal",
                        }
                        order_priority = priority_map.get(ai_priority, "Normal")

                        reason_parts = []
                        if order_ai.get("summary"):
                            reason_parts.append(str(order_ai["summary"]))
                        if order_ai.get("opportunity_reason"):
                            reason_parts.append(
                                "Signals: " + str(order_ai["opportunity_reason"])
                            )
                        if order_ai.get("recurrence_detected"):
                            reason_parts.append("Same-category history detected.")
                        ai_reason = " ".join(reason_parts).strip()

                        order_id = db.create_order(
                            outlet_id=selected_outlet_id,
                            ds_name=ds_name,
                            source="Retailer dashboard",
                            area=area,
                            priority=order_priority,
                            ai_reason=ai_reason,
                            requested_by="Retailer",
                        )

                        for product_id, pname, qty in order_rows:
                            db.add_order_item(
                                order_id,
                                product_id,
                                qty,
                            )

                        st.success(
                            f"Order {order_id} submitted successfully and routed to "
                            f"{ds_name or 'DS queue'}."
                        )



                except Exception as e:
                    st.error(f"Order creation failed: {e}")

        st.divider()

        st.markdown("### DS order queue")
        st.caption("Only AE-approved orders are released for DS execution.")

        all_orders = db.get_orders()

        # DS can execute only orders explicitly approved by the Area Executive.
        orders = [
            o for o in all_orders
            if str(o.get("ae_decision", "")).strip().lower() == "approve"
        ]

        if not orders:
            st.info("No AE-approved orders are currently ready for DS execution.")
        else:
            df_orders = pd.DataFrame(orders)

            display_cols = [
                "order_id",
                "outlet_id",
                "area",
                "ds_name",
                "items",
                "status",
                "ae_decision",
                "created_at",
            ]

            available_cols = [
                c for c in display_cols
                if c in df_orders.columns
            ]

            st.dataframe(
                df_orders[available_cols],
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("### DS execution status")

            order_ids = [o["order_id"] for o in orders]

            selected_order = st.selectbox(
                "Approved order",
                order_ids,
                key="order_status_id",
            )

            selected_status = st.selectbox(
                "Execution status",
                [
                    "Accepted",
                    "Dispatched",
                    "Delivered",
                ],
                key="order_status_value",
            )

            if st.button(
                "Update DS Execution Status",
                key="update_order_status_main",
            ):
                db.update_order_status(
                    selected_order,
                    selected_status,
                )
                st.success(
                    f"{selected_order} updated to {selected_status}."
                )
                st.rerun()

# ---------- TAB 3 ----------
with tabs[2]:
    st.subheader("Issues & historical memory")
    issues = db.get_all_issues()
    if issues:
        st.dataframe(pd.DataFrame(issues), use_container_width=True)
    else:
        st.info("No issues saved yet.")

    st.divider()
    st.subheader("Visit history")
    visits = db.get_visits()
    if visits:
        st.dataframe(pd.DataFrame(visits), use_container_width=True)
    else:
        st.info("No visits saved yet.")

# ---------- TAB 4 ----------
with tabs[3]:
    st.subheader("Area Executive dashboard")
    st.caption(
        "Human decision-maker view: AI recommends, AE decides, DS executes."
    )

    issues = pd.DataFrame(db.get_all_issues())
    orders = pd.DataFrame(db.get_orders())
    visits = pd.DataFrame(db.get_visits())

    # ---------- AE OVERVIEW ----------
    pending_ae = (
        orders[orders["ae_decision"].fillna("").eq("")]
        if not orders.empty and "ae_decision" in orders.columns
        else pd.DataFrame()
    )

    a, b, c, d = st.columns(4)
    a.metric("Orders", len(orders))
    b.metric("AE review pending", len(pending_ae))
    c.metric(
        "Open issues",
        int((issues["status"] == "Open").sum()) if not issues.empty else 0,
    )
    d.metric(
        "P1 issues",
        int((issues["priority"] == "P1").sum()) if not issues.empty else 0,
    )

    # ---------- AE ORDER REVIEW ----------
    st.markdown("### AE order review")

    if orders.empty:
        st.info("No retailer orders available for AE review.")
    elif pending_ae.empty:
        st.success("No orders are currently waiting for AE decision.")
    else:
        order_ids = pending_ae["order_id"].tolist()

        selected_ae_order = st.selectbox(
            "Order awaiting AE decision",
            order_ids,
            key="ae_review_order",
        )

        selected_row = pending_ae[
            pending_ae["order_id"] == selected_ae_order
        ].iloc[0]

        outlet_record = db.get_outlet(selected_row["outlet_id"]) or {}

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Outlet", outlet_record.get("outlet_name", selected_row["outlet_id"]))
        r2.metric("Area", selected_row.get("area") or outlet_record.get("area") or "Not mapped")
        r3.metric("DS", selected_row.get("ds_name") or "Not assigned")
        r4.metric("Priority", selected_row.get("priority") or "Normal")

        st.write(
            f"**Order:** {selected_row['order_id']}  |  "
            f"**Items:** {selected_row.get('items', 'Not available')}"
        )

        ai_reason = selected_row.get("ai_reason") or ""
        if ai_reason:
            st.info(f"AI recommendation / reasoning: {ai_reason}")
        else:
            st.info(
                "AI recommendation is not yet available for this order. "
                "AE should review the retailer request using business judgement."
            )

        decision = st.selectbox(
            "AE decision",
            [
                "Approve",
                "Reject",
                "Needs Clarification",
            ],
            key="ae_decision_value",
        )

        notes = st.text_area(
            "AE notes / decision rationale",
            key="ae_decision_notes",
            placeholder="Why was this decision taken?",
        )

        if st.button(
            "Save AE Decision",
            type="primary",
            use_container_width=True,
            key="save_ae_decision",
        ):
            try:
                db.update_ae_decision(
                    selected_ae_order,
                    decision,
                    notes.strip(),
                )

                st.success(
                    f"{selected_ae_order}: AE decision '{decision}' saved successfully."
                )
                st.rerun()

            except Exception as e:
                st.error(f"AE decision save failed: {e}")

    # ---------- ALL ORDERS ----------
    st.markdown("### Order decision history")

    if not orders.empty:
        history_cols = [
            "order_id",
            "outlet_id",
            "ds_name",
            "area",
            "items",
            "priority",
            "status",
            "ae_decision",
            "ae_decided_at",
            "ae_notes",
        ]

        available_history_cols = [
            c for c in history_cols
            if c in orders.columns
        ]

        st.dataframe(
            orders[available_history_cols],
            use_container_width=True,
            hide_index=True,
        )

    # ---------- ISSUE / FIELD EXCEPTIONS ----------
    if not issues.empty:
        st.markdown("### Priority issue queue")

        priority_issues = issues[
            issues["priority"].isin(["P1", "P2"])
        ]

        if priority_issues.empty:
            st.info("No P1/P2 issues currently open.")
        else:
            st.dataframe(
                priority_issues[
                    [
                        "issue_id",
                        "outlet_id",
                        "category",
                        "priority",
                        "summary",
                        "assigned_owner",
                        "status",
                    ]
                ],
                use_container_width=True,
            )

    st.markdown("### Area / outlet exceptions")

    outlet_df = pd.DataFrame(db.list_outlets())

    if not outlet_df.empty:
        st.dataframe(
            outlet_df,
            use_container_width=True,
            hide_index=True,
        )

# ---------- TAB 5 ----------
with tabs[4]:
    st.subheader("Management analytics")
    issues = pd.DataFrame(db.get_all_issues())
    visits = pd.DataFrame(db.get_visits())
    orders = pd.DataFrame(db.get_orders())

    if issues.empty:
        st.info("Save a few visits to populate analytics.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total issues", len(issues))
        c2.metric("Resolved", int((issues["status"] == "Resolved").sum()))
        c3.metric("P1", int((issues["priority"] == "P1").sum()))

        st.markdown("### Issues by category")
        st.bar_chart(issues["category"].value_counts())

        st.markdown("### Issues by area")
        merged = issues.merge(
            pd.DataFrame(db.list_outlets())[["outlet_id", "area"]],
            on="outlet_id",
            how="left",
        )
        st.bar_chart(merged["area"].fillna("Unknown").value_counts())

        if not orders.empty:
            st.markdown("### Order status")
            st.bar_chart(orders["status"].value_counts())

        if not visits.empty:
            st.markdown("### Visits over time")
            visits["visit_date"] = pd.to_datetime(visits["visit_date"])
            daily = visits.groupby("visit_date").size()
            st.line_chart(daily)

# ---------- TAB 6 ----------
with tabs[5]:
    st.subheader("Excel / data import")
    st.write(
        "Upload the outlet/area Excel sheet here. The importer keeps the original information and "
        "maps common column names into the prototype database."
    )
    uploaded = st.file_uploader("Upload Excel", type=["xlsx", "xls"])
    if uploaded:
        try:
            xls = pd.ExcelFile(uploaded)
            sheet = st.selectbox("Sheet", xls.sheet_names)
            df = pd.read_excel(uploaded, sheet_name=sheet)
            st.write("Preview")
            st.dataframe(df.head(20), use_container_width=True)

            if st.button("Import this sheet"):
                result = db.import_outlet_dataframe(df)
                st.success(
                    f"Imported {result['outlets']} outlets, {result['products']} products and "
                    f"{result['areas']} area mappings."
                )
                st.json(result)
        except Exception as e:
            st.error(f"Excel import error: {e}")

# ---------- TAB 7 ----------
with tabs[6]:
    st.subheader("Daily market competitiveness")
    st.caption(
        "The prototype supports a configurable market-data API. Until a real authorized API is connected, "
        "the system uses a clearly labelled demo snapshot."
    )

    if st.button("Run market intelligence now"):
        snapshot = market_intel.fetch_and_analyze()
        db.save_market_snapshot(snapshot)
        st.session_state["market_snapshot"] = snapshot

    snapshot = st.session_state.get("market_snapshot") or db.latest_market_snapshot()
    if snapshot:
        st.info(snapshot.get("source_status", "Demo"))
        st.write("**Market signal:**", snapshot.get("summary", "-"))
        st.write("**Competitiveness score:**", snapshot.get("competitiveness_score", "-"))
        st.write("**Recommendation:**", snapshot.get("recommendation", "-"))
        st.caption("Market snapshots are saved to history.")

# ---------- TAB 8 ----------
with tabs[7]:
    st.subheader("Retailer call / message / audio / video")
    st.write(
        "Upload an audio/video recording. If a local speech-to-text engine is installed, "
        "the app transcribes it and sends the transcript through the same AI analysis pipeline."
    )
    media = st.file_uploader(
        "Audio/video",
        type=["wav", "mp3", "m4a", "mp4", "mov", "webm"],
        key="voice_tab",
    )
    if media:
        st.audio(media) if media.type and media.type.startswith("audio") else st.video(media)
        if st.button("Transcribe and analyze"):
            with st.spinner("Transcribing..."):
                result = ai.transcribe_media(media)
            if result.get("ok"):
                st.text_area("Transcript", result["text"], height=180)
                st.info("Now copy/use this transcript in the Visit & AI tab for the full human-in-loop workflow.")
            else:
                st.warning(result.get("message", "Speech-to-text engine is not installed."))

st.divider()
st.caption(
    "Prototype boundary: no direct connection to ITC systems, no automatic business decision, "
    "and no external transmission of company/retailer data unless you explicitly configure an API."
)



