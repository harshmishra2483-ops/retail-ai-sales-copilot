
import os, re, json, tempfile, subprocess
from pathlib import Path
import requests
import database as db

ANTHROPIC_API_KEY=os.environ.get("ANTHROPIC_API_KEY","").strip()
ANTHROPIC_MODEL=os.environ.get("ANTHROPIC_MODEL","claude-sonnet-4-6")

CATEGORIES=[
    "Stock availability","Payment/rent/service issue","Product issue",
    "Visibility/branding issue","Retailer awareness","Scheme/promotion query",
    "Distribution/supply issue","Competitor pressure","Sales opportunity","Other"
]

RESPONSIBLE_FUNCTION_MAP={
    "Stock availability":"Sales/Distribution",
    "Payment/rent/service issue":"Finance/Commercial",
    "Product issue":"Sales/Distribution",
    "Visibility/branding issue":"Trade Marketing",
    "Retailer awareness":"Trade Marketing",
    "Scheme/promotion query":"Trade Marketing",
    "Distribution/supply issue":"Sales/Distribution",
    "Competitor pressure":"Sales/Marketing",
    "Sales opportunity":"Sales",
    "Other":"Area Executive",
}

SIGNALS={
    "stock":["stock","out of stock","stock out","khatam","nahi hai","available nahi","empty shelf","maal khatam","inventory low","inventory khatam"],
    "supply":["supply","delivery","distributor","van","replenish","replenishment","late aata","late aati","late aa raha","nahi aaya","dobara nahi aaya","delay","supply disturb"],
    "competitor":["competitor","marlboro","dusra brand","doosra brand","other brand","rival","competition"],
    "competitor_demand":["marlboro maang","gold flake maang","connect maang","competitor maang","competitor ki demand","dusra brand maang","doosra brand maang","customers marlboro","customer marlboro"],
    "growth":["sales badh","sales increase","increase sales","grow","growth","potential","demand strong","chance hai","opportunity","sale improve","bikri badh","more sales","can sell more"],
    "visibility":["visibility","poster","branding","display","signage","board","counter","shelf","display nahi","display poor","branding weak"],
    "scheme":["scheme","offer","discount","promotion","promo","incentive"],
    "payment":["rent","payment","paisa","kiraya","bill","invoice","credit"],
    "product":["damage","damaged","expired","kharab","quality","defect","leak","taste","pasand nahi","liked nahi","product issue"],
    "awareness":["nahi pata","pata nahi","don't know","unaware","awareness","confused","samajh nahi","information nahi"],
    "ds":["ds nahi aaya","ds nahi aya","salesman nahi aaya","salesperson nahi aaya","visit nahi hua","nahi gaya","gaya nahi"],
    "urgency":["urgent","immediately","abhi","bahut urgent","gussa","angry","band kar dunga","band karunga","stop selling","switch","complaint","three days","teen din","again"],
}

def norm(t): return re.sub(r"\s+"," ",(t or "").lower()).strip()
def profile(t): 
    t=norm(t)
    return {k:[p for p in v if p in t] for k,v in SIGNALS.items()}

def best_category(p):
    scores={
        "Stock availability":len(p["stock"])*4+len(p["supply"]),
        "Distribution/supply issue":len(p["supply"])*4+len(p["stock"]),
        "Competitor pressure":len(p["competitor"])*2+len(p["competitor_demand"])*5,
        "Sales opportunity":len(p["growth"])*4,
        "Visibility/branding issue":len(p["visibility"])*4,
        "Scheme/promotion query":len(p["scheme"])*4,
        "Payment/rent/service issue":len(p["payment"])*4,
        "Product issue":len(p["product"])*4,
        "Retailer awareness":len(p["awareness"])*4,
    }
    return max(scores,key=scores.get) if max(scores.values()) else "Other"

def classify(text):
    p=profile(text)
    is_order_request = "retailer order request:" in norm(text)
    category = "Sales opportunity" if is_order_request else best_category(p)
    high=bool(p["urgency"])
    medium=bool(p["stock"] or p["supply"] or p["competitor_demand"] or p["ds"])
    severity="High" if high else ("Medium" if medium else "Low")
    priority={"High":"P1","Medium":"P2","Low":"P3"}[severity]

    parts=[]
    if p["stock"]: parts.append("Stock/availability concern")
    if p["supply"]: parts.append("Supply/replenishment concern")
    if p["competitor_demand"]: parts.append("Competitor-driven demand")
    elif p["competitor"]: parts.append("Competitor pressure")
    if p["visibility"]: parts.append("Visibility/branding concern")
    if p["ds"]: parts.append("DS visit/attendance concern")
    if is_order_request:
        parts.append("Retailer product order request")
    summary=", ".join(parts) or text[:140]

    actions={
        "Stock availability":"Check product-wise stock requirement, confirm replenishment and route the order to the DS.",
        "Visibility/branding issue":"Verify the visibility complaint and assign a Trade Marketing correction.",
        "Distribution/supply issue":"Verify distributor service level and expected replenishment date.",
        "Competitor pressure":"Identify the competitor demand reason and evaluate the relevant portfolio response.",
        "Payment/rent/service issue":"Route the issue to Finance/Commercial for verification.",
        "Product issue":"Verify the product complaint and route it for appropriate review.",
        "Retailer awareness":"Provide the required scheme/product information and confirm retailer understanding.",
        "Scheme/promotion query":"Verify the current scheme and communicate the approved offer.",
        "Sales opportunity":"Validate demand and define a measurable follow-up target.",
        "Other":"Ask for clarification and keep human review mandatory.",
    }
    opportunity=0
    if p["stock"]: opportunity+=20
    if p["supply"]: opportunity+=10
    if p["competitor_demand"]: opportunity+=25
    if p["growth"]: opportunity+=25
    if p["competitor"] and not p["competitor_demand"]: opportunity+=10
    if is_order_request: opportunity+=30

    confidence="High (local signal engine)" if sum(map(len,p.values()))>=3 else ("Medium (local signal engine)" if sum(map(len,p.values())) else "Low (local signal engine)")

    return {
        "category":category,"sub_category":"Product-specific" if p["stock"] else "General",
        "product_service":"Not specified","severity":severity,"priority":priority,
        "sentiment":"Negative/concerned" if high else "Neutral/exploratory",
        "summary":summary,"recommended_action":actions[category],
        "responsible_function":RESPONSIBLE_FUNCTION_MAP[category],
        "opportunity_score":min(100,opportunity),
        "opportunity_reason":"; ".join(parts) or "No strong opportunity signal detected",
        "ai_confidence":confidence,"mode":"local",
        "_profile":p
    }

def same_category_recurrence(outlet_id,text,top_k=3):
    current=classify(text); cat=current["category"]
    curp=current["_profile"]
    past=[]
    for issue in db.get_issues_by_outlet(outlet_id):
        # IMPORTANT: category is determined from the historical issue's own AI classification,
        # never from unrelated structured fields.
        if issue.get("category") != cat:
            continue
        past_text=issue.get("raw_feedback","")
        pp=profile(past_text)
        signal_overlap=sum(1 for k in curp if curp[k] and pp[k])
        token_overlap=len(set(norm(text).split()) & set(norm(past_text).split()))
        score=signal_overlap*6+token_overlap
        if score>=5:
            past.append((score,issue))
    past.sort(key=lambda x:(x[0],x[1].get("visit_date","")),reverse=True)
    top=[x[1] for x in past[:top_k]]
    if not top:
        return [],"No same-category past issue found at this outlet."
    return top,"Same-category recurrence detected:\n"+"\n".join(
        f"- {i.get('category')} on {i.get('visit_date')}: {i.get('summary') or i.get('raw_feedback','')}"
        for i in top
    )

def llm_classify(text,context,outlet):
    if not ANTHROPIC_API_KEY: return None
    prompt=f"""You are a retail field-sales copilot.
Return JSON only with category, sub_category, product_service, severity, priority,
sentiment, summary, recommended_action, responsible_function, opportunity_score,
opportunity_reason, ai_confidence.
Do not invent facts. Human approval is mandatory.
Allowed categories: {CATEGORIES}
Outlet: {json.dumps(outlet,ensure_ascii=False)}
Current feedback: {text}
Relevant same-category history: {context}
"""
    try:
        r=requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            json={"model":ANTHROPIC_MODEL,"max_tokens":800,"messages":[{"role":"user","content":prompt}]},
            timeout=20)
        r.raise_for_status()
        raw="".join(x["text"] for x in r.json().get("content",[]) if x.get("type")=="text").strip()
        raw=re.sub(r"^```json|```$","",raw,flags=re.MULTILINE).strip()
        out=json.loads(raw); out["mode"]="live"
        out["responsible_function"]=RESPONSIBLE_FUNCTION_MAP.get(out.get("category","Other"),"Area Executive")
        return out
    except Exception:
        return None

def analyze_visit(outlet_id,feedback,stock_rows=None,order_rows=None):
    outlet=db.get_outlet(outlet_id) or {}
    result=classify(feedback)
    similar,context=same_category_recurrence(outlet_id,feedback)
    live=llm_classify(feedback,context,outlet)
    if live:
        result.update(live)
    result["similar_past_issue_ids"]=",".join(i["issue_id"] for i in similar)
    result["similar_context"]=context
    result["recurrence_detected"]=bool(similar)

    alerts=[]
    order_stock_gaps=[]
    requested_by_product={str(pid): int(qty) for pid,pname,qty in (order_rows or [])}

    for pid,pname,qty in stock_rows or []:
        pid_key=str(pid)

        if order_rows and pid_key not in requested_by_product:
            continue

        if qty<=0:
            alerts.append(f"{pname}: out of stock")
        elif qty<=5:
            alerts.append(f"{pname}: low stock ({qty})")

        if pid_key in requested_by_product:
            requested_qty=requested_by_product[pid_key]
            gap=max(0,requested_qty-int(qty))
            if gap>0:
                order_stock_gaps.append(
                    f"{pname}: requested {requested_qty}, stock {qty}, replenishment gap {gap}"
                )

    if alerts:
        result["opportunity_score"]=min(100,int(result.get("opportunity_score",0))+10)

    if order_stock_gaps:
        result["opportunity_score"]=min(100,int(result.get("opportunity_score",0))+20)

        existing_reason=str(result.get("opportunity_reason","")).strip()
        result["opportunity_reason"]=(existing_reason + " Stock-demand gap").strip()

        if str(result.get("priority","P3")).upper() in {"P3","LOW"}:
            result["priority"]="P2"

        existing_summary=str(result.get("summary","")).strip()
        result["summary"]=(existing_summary + " Stock-demand gap identified for ordered product(s).").strip()

    result["stock_alerts"]=alerts
    result["order_stock_gaps"]=order_stock_gaps

    actions=[result["recommended_action"]]
    if result["recurrence_detected"]: actions.append("Review the same-category history and confirm whether the previous root cause was resolved.")
    if alerts: actions.append("Route product-wise replenishment requirement to the DS.")
    if order_stock_gaps: actions.append("Review the ordered product stock-demand gap before approving replenishment.")
    if result["priority"]=="P1": actions.append("Escalate to Area Executive for human review.")
    result["next_best_actions"]=list(dict.fromkeys(actions))
    return result

def transcribe_media(uploaded_file):
    try:
        import speech_recognition as sr
    except Exception:
        return {"ok":False,"message":"SpeechRecognition is not installed. The Voice/Video tab is ready, but local transcription needs the optional package."}

    suffix=Path(uploaded_file.name).suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False,suffix=suffix) as f:
        f.write(uploaded_file.getbuffer()); path=f.name
    try:
        if suffix.lower() not in [".wav",".aiff",".flac"]:
            return {"ok":False,"message":"For tomorrow's prototype, upload WAV audio for direct local transcription. MP3/M4A/video conversion can be enabled later with FFmpeg."}
        r=sr.Recognizer()
        with sr.AudioFile(path) as source:
            audio=r.record(source)
        text=r.recognize_google(audio,language="hi-IN")
        return {"ok":True,"text":text}
    except Exception as e:
        return {"ok":False,"message":f"Transcription could not be completed: {e}"}
    finally:
        try: os.remove(path)
        except: pass

def generate_escalation_draft(issue):
    return f"""Subject: Retail issue - {issue.get('category')} [{issue.get('priority')}]

Outlet: {issue.get('outlet_id')}
Summary: {issue.get('summary')}
Recommended action: {issue.get('recommended_action')}
Assigned owner: {issue.get('assigned_owner')}

AI-generated draft. Human approval is required before action."""
