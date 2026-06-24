from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_file
import anthropic
import json
import re
import os
import io
from datetime import date
from database import get_db, init_db

app = Flask(__name__)
_claude = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from env

with app.app_context():
    init_db()

def _clean(value, max_len=500):
    return str(value).strip()[:max_len]

@app.route("/export/pdf", methods=["POST"])
def export_pdf():
    from fpdf import FPDF

    data       = request.get_json(silent=True) or {}
    brief_text = _clean(data.get("brief_text", ""), max_len=50000)
    org_name   = _clean(data.get("org_name",   "Campaign Brief"), max_len=200)
    tone       = _clean(data.get("tone",        ""), max_len=100)
    platforms  = [_clean(p, 50) for p in data.get("platforms", []) if isinstance(p, str)][:10]

    if not brief_text:
        return jsonify({"error": "No brief text provided."}), 400

    today = date.today().strftime("%d %B %Y").lstrip("0")

    INDIGO = (79, 70, 229)
    DARK   = (26, 26, 46)
    GRAY   = (107, 114, 128)
    LIGHT  = (156, 163, 175)
    MID    = (55, 65, 81)
    LH     = 5.5   # base line height in mm

    class BriefPDF(FPDF):
        def footer(self):
            self.set_y(-14)
            self.set_font('Helvetica', 'I', 7.5)
            self.set_text_color(*LIGHT)
            self.cell(0, 10, f'{org_name}  ·  Campaign Brief  ·  Page {self.page_no()}', align='C')

    pdf = BriefPDF(orientation='P', unit='mm', format='A4')
    pdf.set_margins(left=25, top=22, right=25)
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.add_page()

    # ── Document header ──────────────────────────────────────────────────────
    pdf.set_font('Helvetica', 'B', 22)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(0, 11, org_name, align='L')
    pdf.ln(2)

    meta_y = pdf.get_y()
    meta_x = pdf.l_margin

    if tone:
        badge_text = tone.upper()
        pdf.set_font('Helvetica', 'B', 7)
        bw = pdf.get_string_width(badge_text) + 7
        pdf.set_fill_color(*INDIGO)
        pdf.set_text_color(255, 255, 255)
        pdf.rect(meta_x, meta_y, bw, 5.5, 'F')
        pdf.set_xy(meta_x, meta_y)
        pdf.cell(bw, 5.5, badge_text, align='C')
        meta_x += bw + 5

    pdf.set_xy(meta_x, meta_y)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 5.5, today, ln=True)

    if platforms:
        pdf.ln(1)
        pdf.set_font('Helvetica', '', 8.5)
        pdf.set_text_color(*LIGHT)
        pdf.multi_cell(0, 5, '  ·  '.join(platforms), align='L')

    pdf.ln(4)
    div_y = pdf.get_y()
    pdf.set_draw_color(*INDIGO)
    pdf.set_line_width(0.5)
    pdf.line(pdf.l_margin, div_y, pdf.w - pdf.r_margin, div_y)
    pdf.ln(6)

    # ── Brief content ────────────────────────────────────────────────────────
    in_ul = in_ol = False
    ol_num = 0
    INDENT = 7

    def close_lists():
        nonlocal in_ul, in_ol, ol_num
        if in_ul or in_ol:
            pdf.ln(1.5)
        in_ul = in_ol = False
        ol_num = 0

    def write_inline(txt, sz=9.5):
        for part in re.split(r'(\*\*[^*]+\*\*|\*[^*]+\*)', txt):
            if part.startswith('**') and part.endswith('**'):
                pdf.set_font('Helvetica', 'B', sz); pdf.write(LH, part[2:-2])
            elif part.startswith('*') and part.endswith('*'):
                pdf.set_font('Helvetica', 'I', sz); pdf.write(LH, part[1:-1])
            else:
                pdf.set_font('Helvetica', '', sz);  pdf.write(LH, part)

    for line in brief_text.split('\n'):
        s     = line.strip()
        is_ul = s.startswith('- ') or s.startswith('* ')
        is_ol = bool(re.match(r'^\d+\.\s', s))

        if not is_ul and in_ul: close_lists()
        if not is_ol and in_ol: close_lists()

        if not s:
            continue

        if s.startswith('## '):
            close_lists()
            pdf.ln(4)
            orig = pdf.l_margin
            y    = pdf.get_y()
            pdf.set_fill_color(*INDIGO)
            pdf.rect(orig, y, 2.5, 7, 'F')
            pdf.set_left_margin(orig + 5)
            pdf.set_x(orig + 5)
            pdf.set_font('Helvetica', 'B', 11.5)
            pdf.set_text_color(*DARK)
            pdf.multi_cell(0, 7, s[3:], align='L')
            pdf.set_left_margin(orig)
            pdf.ln(2)

        elif s.startswith('### '):
            close_lists()
            pdf.ln(2)
            pdf.set_font('Helvetica', 'B', 10)
            pdf.set_text_color(*MID)
            pdf.multi_cell(0, LH, s[4:], align='L')
            pdf.ln(1)

        elif is_ul:
            if not in_ul: in_ul = True
            orig = pdf.l_margin
            pdf.set_left_margin(orig + INDENT + 4)
            pdf.set_xy(orig + INDENT, pdf.get_y())
            pdf.set_font('Helvetica', '', 9.5)
            pdf.set_text_color(*INDIGO)
            pdf.cell(4, LH, '\xb7')
            pdf.set_text_color(*DARK)
            write_inline(s[2:])
            pdf.ln()
            pdf.set_left_margin(orig)

        elif is_ol:
            if not in_ol: in_ol = True
            ol_num += 1
            content = re.sub(r'^\d+\.\s+', '', s)
            orig    = pdf.l_margin
            num_str = f'{ol_num}.'
            pdf.set_font('Helvetica', 'B', 9.5)
            nw = pdf.get_string_width(num_str) + 2
            pdf.set_left_margin(orig + INDENT + nw)
            pdf.set_xy(orig + INDENT, pdf.get_y())
            pdf.set_text_color(*INDIGO)
            pdf.cell(nw, LH, num_str)
            pdf.set_text_color(*DARK)
            write_inline(content)
            pdf.ln()
            pdf.set_left_margin(orig)

        else:
            close_lists()
            pdf.set_text_color(*DARK)
            write_inline(s)
            pdf.ln()
            pdf.ln(1.5)

    filename = re.sub(r'[^a-z0-9]+', '_', org_name.lower()).strip('_') + '_brief.pdf'

    return send_file(
        io.BytesIO(bytes(pdf.output())),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/personas", methods=["POST"])
def personas():
    data     = request.get_json(silent=True) or {}
    org_name = _clean(data.get("org_name", ""), max_len=200)
    cause    = _clean(data.get("cause",    ""), max_len=300)
    audience = _clean(data.get("audience", ""), max_len=200)
    tone     = _clean(data.get("tone",     ""), max_len=100)
    goal     = _clean(data.get("goal",     ""), max_len=200)

    if not all([org_name, cause, audience]):
        return jsonify({"error": "Missing required fields."}), 400

    prompt = f"""Generate 2 distinct audience personas for a nonprofit campaign.

Organisation: {org_name}
Cause: {cause}
Target Audience: {audience}
Goal: {goal}
Tone: {tone}

Return ONLY this exact JSON — no markdown, no explanation:
{{
  "personas": [
    {{
      "name": "First name only",
      "age": 28,
      "motivation": "One sentence on what drives them to care about this cause",
      "barrier": "One sentence on what stops them from taking action"
    }},
    {{
      "name": "First name only",
      "age": 42,
      "motivation": "One sentence on what drives them to care about this cause",
      "barrier": "One sentence on what stops them from taking action"
    }}
  ]
}}"""

    try:
        result = _claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text  = result.content[0].text.strip()
        text  = re.sub(r'```(?:json)?\s*', '', text).strip().rstrip('`').strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            obj  = json.loads(match.group())
            validated = []
            for p in obj.get("personas", [])[:2]:
                try:
                    age = int(p.get("age", 30))
                except (ValueError, TypeError):
                    age = 30
                validated.append({
                    "name":       _clean(str(p.get("name",       "")), 50),
                    "age":        age,
                    "motivation": _clean(str(p.get("motivation", "")), 300),
                    "barrier":    _clean(str(p.get("barrier",    "")), 300),
                })
            return jsonify({"personas": validated})
    except Exception:
        pass
    return jsonify({"personas": []}), 500


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}

    org_name  = _clean(data.get("org_name", ""))
    cause     = _clean(data.get("cause", ""))
    audience  = _clean(data.get("audience", ""))
    tone      = _clean(data.get("tone", ""))
    goal      = _clean(data.get("goal", ""))
    platforms = [
        _clean(p, 50) for p in data.get("platforms", [])
        if isinstance(p, str)
    ][:10]

    style_modifier = _clean(data.get("style_modifier", ""), max_len=400)

    personas = []
    for p in data.get("personas", [])[:2]:
        if isinstance(p, dict):
            try:
                age = int(p.get("age", 30))
            except (ValueError, TypeError):
                age = 30
            personas.append({
                "name":       _clean(str(p.get("name",       "")), 50),
                "age":        age,
                "motivation": _clean(str(p.get("motivation", "")), 300),
                "barrier":    _clean(str(p.get("barrier",    "")), 300),
            })

    if personas:
        persona_lines = "\n".join(
            f"  • {p['name']}, age {p['age']}: Motivated by — {p['motivation']} | Barrier — {p['barrier']}"
            for p in personas
        )
        persona_context = f"\nAudience Personas (tailor all messaging to address their motivations and barriers):\n{persona_lines}\n"
    else:
        persona_context = ""

    try:
        org_id = int(data.get("org_id") or 0)
    except (ValueError, TypeError):
        org_id = 0

    org_context = ""
    if org_id:
        org_row = get_db().execute("SELECT * FROM orgs WHERE id=?", (org_id,)).fetchone()
        if org_row:
            org_d = dict(org_row)
            ctx = []
            if org_d.get("brand_voice"):
                ctx.append(f"Brand Voice: {_clean(org_d['brand_voice'], 300)}")
            try:
                campaigns = json.loads(org_d.get("past_campaigns") or "[]")
            except Exception:
                campaigns = []
            if campaigns:
                clist = "; ".join(_clean(str(c), 150) for c in campaigns[:10])
                ctx.append(f"Past Campaigns (do not repeat these ideas or approaches): {clist}")
            if ctx:
                org_context = "\n" + "\n".join(ctx)

    if not all([org_name, cause, audience, tone, goal]) or not platforms:
        return jsonify({"error": "All fields are required."}), 400

    prompt = f"""You are an expert nonprofit marketing strategist. Generate a comprehensive campaign brief for the following organisation.

Organisation: {org_name}
Cause / Mission: {cause}
Target Audience: {audience}
Campaign Goal: {goal}
Tone: {tone}
Platforms: {", ".join(platforms)}{persona_context}{org_context}
Produce a campaign brief with exactly these sections:

## Campaign Overview
A 2-3 sentence summary of the campaign strategy.

## Key Messages
3 core messages that will resonate with the target audience. Each as a punchy one-liner.

## Content Ideas
One specific content idea per platform selected, with a brief description of what it looks like in practice.

## Sample Copy
Write one ready-to-use piece of copy for the first platform listed. Make it feel real and compelling — not generic.

## Content Calendar (4 weeks)
A simple week-by-week outline showing what to post and when.

## Success Metrics
3-4 specific, measurable metrics to track campaign performance.

Be specific, practical, and tailored to a nonprofit context. Avoid corporate jargon."""

    if style_modifier:
        prompt += f"\n\nAdditional style direction: {style_modifier}"

    def stream():
        try:
            with _claude.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            ) as s:
                for chunk in s.text_stream:
                    yield chunk
        except anthropic.AuthenticationError:
            yield "\n[Error: Invalid or missing ANTHROPIC_API_KEY.]"
        except Exception as e:
            yield f"\n[Error: {e}]"

    return Response(
        stream_with_context(stream()),
        content_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.route("/suggestions", methods=["POST"])
def suggestions():
    data     = request.get_json(silent=True) or {}
    org_name = _clean(data.get("org_name", ""), max_len=200)
    cause    = _clean(data.get("cause", ""),    max_len=300)
    goal     = _clean(data.get("goal", ""),     max_len=200)

    prompt = f"""For a nonprofit called "{org_name}" focused on: "{cause}" with goal: "{goal}", return discovery resources so their team can find recent work, news, and video inspiration.

Return ONLY this exact JSON object — no markdown, no explanation:
{{
  "youtube": ["2 specific YouTube search queries for volunteer stories and campaign videos"],
  "news": ["2 Google News search queries for recent coverage of this cause"],
  "hashtags": ["4 relevant social media hashtags without the # symbol"]
}}"""

    try:
        result = _claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text  = result.content[0].text.strip()
        text  = re.sub(r'```(?:json)?\s*', '', text).strip().rstrip('`').strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            obj = json.loads(match.group())
            return jsonify({
                "youtube":  [str(q) for q in obj.get("youtube",  [])[:3]],
                "news":     [str(q) for q in obj.get("news",     [])[:3]],
                "hashtags": [str(h).lstrip('#') for h in obj.get("hashtags", [])[:4]],
            })
    except Exception:
        pass
    return jsonify({"youtube": [], "news": [], "hashtags": []})


@app.route("/visuals", methods=["POST"])
def visuals():
    data       = request.get_json(silent=True) or {}
    org_name   = _clean(data.get("org_name",   ""), max_len=200)
    cause      = _clean(data.get("cause",      ""), max_len=300)
    tone       = _clean(data.get("tone",       ""), max_len=100)
    goal       = _clean(data.get("goal",       ""), max_len=200)
    brief_text = _clean(data.get("brief_text", ""), max_len=3000)
    platforms  = [
        _clean(p, 50) for p in data.get("platforms", [])
        if isinstance(p, str)
    ][:10]

    if not platforms:
        return jsonify({"error": "No platforms provided."}), 400

    platform_list = "\n".join(f"- {p}" for p in platforms)

    prompt = f"""You are a visual art director for nonprofit social media campaigns.

Campaign context:
Organisation: {org_name}
Cause: {cause}
Goal: {goal}
Tone: {tone}
Brief excerpt: {brief_text[:500]}

For each platform below, write a single image-generation prompt (15–25 words) that would produce an ideal campaign visual. Match the platform's visual culture. No text or typography in the image. Be specific about mood, colour palette, composition, and style.

Platforms:
{platform_list}

Return ONLY this exact JSON — no markdown, no explanation:
{{
  "visuals": [
    {{"platform": "platform name exactly as listed", "prompt": "image generation prompt"}},
    ...
  ]
}}"""

    try:
        result = _claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text  = result.content[0].text.strip()
        text  = re.sub(r'```(?:json)?\s*', '', text).strip().rstrip('`').strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            obj = json.loads(match.group())
            validated = [
                {
                    "platform": _clean(str(v.get("platform", "")), 50),
                    "prompt":   _clean(str(v.get("prompt",   "")), 300),
                }
                for v in obj.get("visuals", [])[:len(platforms)]
                if v.get("prompt")
            ]
            return jsonify({"visuals": validated})
    except Exception:
        pass
    return jsonify({"visuals": []}), 500


@app.route("/tweak", methods=["POST"])
def tweak():
    data = request.get_json(silent=True) or {}
    brief_text  = _clean(data.get("brief_text",  ""), max_len=10000)
    instruction = _clean(data.get("instruction", ""), max_len=300)

    if not brief_text or not instruction:
        return jsonify({"error": "Missing brief or instruction."}), 400

    prompt = f"""You are an expert nonprofit marketing strategist. Below is an existing campaign brief that needs to be refined.

EXISTING BRIEF:
{brief_text}

INSTRUCTION: {instruction}

Rewrite the brief following the instruction above. Keep the same ## section headings and overall structure. Return only the revised brief — no preamble, no explanation."""

    def stream():
        try:
            with _claude.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            ) as s:
                for chunk in s.text_stream:
                    yield chunk
        except anthropic.AuthenticationError:
            yield "\n[Error: Invalid or missing ANTHROPIC_API_KEY.]"
        except Exception as e:
            yield f"\n[Error: {e}]"

    return Response(
        stream_with_context(stream()),
        content_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/save", methods=["POST"])
def save():
    data = request.get_json(silent=True) or {}

    org_name   = _clean(data.get("org_name", ""))
    cause      = _clean(data.get("cause", ""))
    audience   = _clean(data.get("audience", ""))
    tone       = _clean(data.get("tone", ""))
    goal       = _clean(data.get("goal", ""))
    brief_text = _clean(data.get("brief_text", ""), max_len=50000)
    platforms  = [
        _clean(p, 50) for p in data.get("platforms", [])
        if isinstance(p, str)
    ][:10]

    if not all([org_name, cause, audience, tone, goal, brief_text]) or not platforms:
        return jsonify({"error": "Missing required fields."}), 400

    db = get_db()
    db.execute(
        """INSERT INTO briefs (org_name, cause, audience, tone, platforms, goal, brief_text)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (org_name, cause, audience, tone, ",".join(platforms), goal, brief_text),
    )
    db.commit()
    return jsonify({"status": "saved"}), 201


@app.route("/history", methods=["GET"])
def history():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM briefs ORDER BY created_at DESC"
    ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/orgs-page")
def orgs_page():
    return render_template("orgs.html")


@app.route("/orgs", methods=["GET"])
def list_orgs():
    db = get_db()
    rows = db.execute("SELECT * FROM orgs ORDER BY name COLLATE NOCASE").fetchall()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["past_campaigns"] = json.loads(d.get("past_campaigns") or "[]")
        except Exception:
            d["past_campaigns"] = []
        result.append(d)
    return jsonify(result)


@app.route("/orgs", methods=["POST"])
def create_org():
    data            = request.get_json(silent=True) or {}
    name            = _clean(data.get("name",            ""), max_len=200)
    mission         = _clean(data.get("mission",         ""), max_len=1000)
    brand_voice     = _clean(data.get("brand_voice",     ""), max_len=500)
    target_audience = _clean(data.get("target_audience", ""), max_len=300)
    past_campaigns  = data.get("past_campaigns", [])
    if not isinstance(past_campaigns, list):
        past_campaigns = []
    past_campaigns = [_clean(str(c), 300) for c in past_campaigns[:20] if str(c).strip()]

    if not name:
        return jsonify({"error": "Name is required."}), 400

    db  = get_db()
    cur = db.execute(
        "INSERT INTO orgs (name, mission, brand_voice, target_audience, past_campaigns) VALUES (?,?,?,?,?)",
        (name, mission, brand_voice, target_audience, json.dumps(past_campaigns)),
    )
    db.commit()
    return jsonify({"id": cur.lastrowid, "status": "created"}), 201


@app.route("/orgs/<int:org_id>", methods=["PUT"])
def update_org(org_id):
    data            = request.get_json(silent=True) or {}
    name            = _clean(data.get("name",            ""), max_len=200)
    mission         = _clean(data.get("mission",         ""), max_len=1000)
    brand_voice     = _clean(data.get("brand_voice",     ""), max_len=500)
    target_audience = _clean(data.get("target_audience", ""), max_len=300)
    past_campaigns  = data.get("past_campaigns", [])
    if not isinstance(past_campaigns, list):
        past_campaigns = []
    past_campaigns = [_clean(str(c), 300) for c in past_campaigns[:20] if str(c).strip()]

    if not name:
        return jsonify({"error": "Name is required."}), 400

    db = get_db()
    db.execute(
        "UPDATE orgs SET name=?, mission=?, brand_voice=?, target_audience=?, past_campaigns=? WHERE id=?",
        (name, mission, brand_voice, target_audience, json.dumps(past_campaigns), org_id),
    )
    db.commit()
    return jsonify({"status": "updated"})


@app.route("/orgs/<int:org_id>", methods=["DELETE"])
def delete_org(org_id):
    db = get_db()
    db.execute("DELETE FROM orgs WHERE id=?", (org_id,))
    db.commit()
    return jsonify({"status": "deleted"})


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port  = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
