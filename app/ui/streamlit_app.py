import streamlit as st

from app.database.connection import SessionLocal
from app.database.repository import (
    create_check_request,
    create_check_result,
    create_response_log,
    update_check_result_ai_summary,
)
from app.services.analysis_service import analyze_preliminary
from app.services.blacklist_flow_service import process_blacklist_check
from app.services.ai_flow_service import process_ai_analysis
from app.utils.input_processor import process_user_input
from app.utils.status_mapper import map_status_to_thai

st.set_page_config(
    page_title="Scam Detection Chatbot",
    page_icon="🛡️",
    layout="centered"
)

st.title("🛡️ Scam Detection Chatbot")
st.write("ระบบช่วยตรวจสอบเบื้องต้นว่าข้อมูลหรือข้อความเข้าข่ายการหลอกลวงออนไลน์หรือไม่")

user_input = st.text_area(
    "กรอกข้อความ / เบอร์โทร / เลขบัญชี / ลิงก์",
    height=150,
    placeholder="เช่น รีบโอนตอนนี้เลย ของมีชิ้นเดียว"
)

if st.button("ตรวจสอบ"):
    if not user_input.strip():
        st.warning("กรุณากรอกข้อมูลก่อน")
    else:
        processed = process_user_input(user_input)

        db = SessionLocal()
        try:
            request_record = create_check_request(
                db=db,
                user_id=None,
                input_type=processed["input_type"],
                input_text=processed["original_input"],
            )

            blacklist_result = process_blacklist_check(
                db=db,
                request_id=request_record.request_id,
                input_type=processed["input_type"],
                normalized_value=processed["normalized_value"],
            )

            # ตรวจ entities ที่ extract ออกมาจาก text
            entity_blacklist_results = []
            for entity in processed.get("extracted_entities", []):
                result = process_blacklist_check(
                    db=db,
                    request_id=request_record.request_id,
                    input_type=entity["type"],
                    normalized_value=entity["value"],
                )
                entity_blacklist_results.append({**entity, **result})
                if result["found"]:
                    blacklist_result["found"] = True
                if result.get("checked", True) and result["status"] != "skipped":
                    blacklist_result["checked"] = True

            analysis_result = analyze_preliminary(
                db=db,
                input_type=processed["input_type"],
                normalized_value=processed["normalized_value"],
                blacklist_found=blacklist_result["found"],
            )

            result_record = create_check_result(
                db=db,
                request_id=request_record.request_id,
                result_status=analysis_result["status"],
                matched_pattern=", ".join(analysis_result["matched_pattern_names"])
                if analysis_result["matched_pattern_names"] else None,
                ai_summary=None,
            )

            ai_result = process_ai_analysis(
                original_input=processed["original_input"],
                input_type=processed["input_type"],
                matched_pattern_names=analysis_result["matched_pattern_names"],
                blacklist_found=blacklist_result["found"],
            )

            if ai_result["success"] and ai_result["summary_text"]:
                update_check_result_ai_summary(
                    db=db,
                    result_id=result_record.result_id,
                    ai_summary=ai_result["summary_text"],
                )

            final_response_text = (
                f"สถานะ: {map_status_to_thai(analysis_result['status'])}\n"
                f"เหตุผล: {analysis_result['reason_text']}\n"
                f"คำแนะนำ: {analysis_result['advice_text']}"
            )

            create_response_log(
                db=db,
                result_id=result_record.result_id,
                response_text=final_response_text,
            )

        finally:
            db.close()

        st.success("วิเคราะห์ข้อมูลสำเร็จ")

        st.subheader("ผลการคัดกรอง")
        st.write(f"**สถานะ:** {map_status_to_thai(analysis_result['status'])}")
        st.write(f"**ประเภทข้อมูล:** {processed['input_type']}")
        st.write(f"**เหตุผล:** {analysis_result['reason_text']}")

        st.subheader("ผลจาก Blacklist API")
        st.write(f"**มีการตรวจสอบ:** {blacklist_result['checked']}")
        st.write(f"**สถานะการเรียก API:** {blacklist_result['status']}")
        st.write(f"**พบข้อมูลใน blacklist:** {blacklist_result['found']}")
        if blacklist_result.get("message"):
            st.write(f"**ข้อความ:** {blacklist_result['message']}")

        if entity_blacklist_results:
            st.write("**ผลตรวจข้อมูลที่พบในข้อความ:**")
            for r in entity_blacklist_results:
                status_icon = "🔴" if r["found"] else "🟢"
                st.write(f"{status_icon} `{r['value']}` ({r['type']}) — {r['status']}")

        st.subheader("Pattern ที่พบ")
        if analysis_result["matched_pattern_names"]:
            for name in analysis_result["matched_pattern_names"]:
                st.write(f"- {name}")
        else:
            st.write("ไม่พบ pattern ชัดเจน")

        st.subheader("คำแนะนำจากระบบ")
        st.write(analysis_result["advice_text"])

        st.subheader("ผลวิเคราะห์จาก AI")
        if ai_result["success"] and ai_result["summary_text"]:
            st.write(ai_result["summary_text"])
        else:
            st.warning(ai_result["message"])

        with st.expander("ดูข้อมูลที่ผ่านการประมวลผล"):
            st.json(processed)

        with st.expander("ดูผลลัพธ์ดิบจาก Blacklist"):
            st.json(blacklist_result)

        with st.expander("ดูผลลัพธ์ดิบจาก AI"):
            st.json(ai_result)