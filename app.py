import streamlit as st
import pandas as pd
import os
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO

# ===================================
# CONFIGURATION (change filenames / admin roll as needed)
# ===================================
ADMIN_ROLL = "ADMIN"                  # change to your admin roll if needed
TEMPLATE_FILE = "certificate_template.pdf"
ALLOWED_ROLLS_FILE = "allowed_rolls.csv"   # should contain a column named 'roll'
USED_ROLLS_FILE = "used_rolls.csv"         # will be created if missing
LORA_BOLD_FONT = "Lora-Bold.ttf"     # optional font file in project folder

st.set_page_config(page_title="🎓 Certificate Portal", page_icon="🎓", layout="centered")
st.title("🎓 Student Certificate Portal (Roll-based one-time login)")

# ===================================
# REGISTER CUSTOM FONT
# ===================================
try:
    if os.path.exists(LORA_BOLD_FONT):
        pdfmetrics.registerFont(TTFont('Lora-Bold', LORA_BOLD_FONT))
        font_name = 'Lora-Bold'
    else:
        st.warning(f"⚠️ {LORA_BOLD_FONT} not found. Using default Helvetica-Bold font.")
        font_name = 'Helvetica-Bold'
except Exception as e:
    st.warning(f"Could not load custom font: {str(e)}. Using default font.")
    font_name = 'Helvetica-Bold'

# ===================================
# INITIALIZE SESSION STATE
# ===================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_roll' not in st.session_state:
    st.session_state.user_roll = ""
if 'certificate_generated' not in st.session_state:
    st.session_state.certificate_generated = False
if 'pdf_data' not in st.session_state:
    st.session_state.pdf_data = None
if 'student_name' not in st.session_state:
    st.session_state.student_name = ""

# ===================================
# CHECK REQUIRED FILES
# ===================================
if not os.path.exists(ALLOWED_ROLLS_FILE):
    st.error(f"⚠️ '{ALLOWED_ROLLS_FILE}' file is missing. Please contact administrator.")
    st.stop()

# Load and validate allowed_rolls.csv
try:
    allowed_rolls = pd.read_csv(ALLOWED_ROLLS_FILE, dtype=str)
    # Ensure 'roll' column exists
    if 'roll' not in allowed_rolls.columns:
        st.error(f"⚠️ The file '{ALLOWED_ROLLS_FILE}' must have a 'roll' column.")
        st.info(f"Current columns found: {list(allowed_rolls.columns)}")
        st.info("Please ensure your CSV has a header row with 'roll' as one of the column names.")
        st.stop()

    # Clean roll column (trim whitespace)
    allowed_rolls['roll'] = allowed_rolls['roll'].astype(str).str.strip()

except Exception as e:
    st.error(f"Error reading {ALLOWED_ROLLS_FILE}: {str(e)}")
    st.stop()

# Create used_rolls file if it doesn't exist
if not os.path.exists(USED_ROLLS_FILE):
    pd.DataFrame(columns=["roll"]).to_csv(USED_ROLLS_FILE, index=False)

try:
    used_rolls = pd.read_csv(USED_ROLLS_FILE, dtype=str)
    if 'roll' in used_rolls.columns and not used_rolls.empty:
        used_rolls['roll'] = used_rolls['roll'].astype(str).str.strip()
    elif 'roll' not in used_rolls.columns:
        used_rolls = pd.DataFrame(columns=["roll"])
except Exception as e:
    st.error(f"Error reading {USED_ROLLS_FILE}: {str(e)}")
    used_rolls = pd.DataFrame(columns=["roll"])

# ===================================
# STUDENT LOGIN (ROLL)
# ===================================
if not st.session_state.logged_in:
    st.subheader("🔐 Student Login (One-time with Roll Number)")

    roll_input = st.text_input("Enter your registered roll number", key="roll_input").strip()

    if st.button("Login", type="primary"):
        if roll_input == "":
            st.warning("⚠️ Please enter your roll number.")
        elif roll_input != ADMIN_ROLL and roll_input not in allowed_rolls['roll'].values:
            st.error("❌ Roll number not found. Please contact your administrator.")
        elif roll_input != ADMIN_ROLL and 'roll' in used_rolls.columns and roll_input in used_rolls['roll'].values:
            st.error("❌ This roll number has already received a certificate.")
        else:
            st.session_state.logged_in = True
            st.session_state.user_roll = roll_input
            st.rerun()

# ===================================
# CERTIFICATE GENERATION
# ===================================
else:
    st.success(f"✅ Welcome, Roll: {st.session_state.user_roll}!")

    # Logout button
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.user_roll = ""
        st.session_state.certificate_generated = False
        st.session_state.pdf_data = None
        st.session_state.student_name = ""
        st.rerun()

    st.divider()
    st.subheader("📜 Generate Your Certificate")

    # Font size adjustment
    font_size = st.slider("Adjust name font size", min_value=24, max_value=60, value=36, step=2)

    name = st.text_input(
        "Enter your full name as it should appear on the certificate",
        value=st.session_state.student_name,
        key="name_input"
    )

    if st.button("🎓 Generate Certificate", type="primary"):
        if name.strip() == "":
            st.warning("⚠️ Please enter your name.")
        elif not os.path.exists(TEMPLATE_FILE):
            st.error("⚠️ Certificate template not found! Add 'certificate_template.pdf' to this folder.")
        else:
            try:
                with st.spinner("Generating your certificate..."):
                    # Create overlay with name
                    packet = BytesIO()
                    can = canvas.Canvas(packet, pagesize=letter)

                    # Set custom font (Lora-Bold or fallback to Helvetica-Bold)
                    can.setFont(font_name, font_size)

                    # Get template dimensions for accurate centering
                    temp_reader = PdfReader(open(TEMPLATE_FILE, "rb"))
                    template_page = temp_reader.pages[0]
                    page_width = float(template_page.mediabox.width)
                    page_height = float(template_page.mediabox.height)

                    # Center position for name (adjust y-coordinate as needed)
                    x = page_width / 2
                    y = page_height / 2  # Adjust this value based on your template design

                    can.drawCentredString(x, y, name.strip())
                    can.save()

                    # Merge overlay with base certificate
                    packet.seek(0)
                    overlay_pdf = PdfReader(packet)
                    existing_pdf = PdfReader(open(TEMPLATE_FILE, "rb"))
                    output = PdfWriter()

                    # Merge pages
                    page = existing_pdf.pages[0]
                    page.merge_page(overlay_pdf.pages[0])
                    output.add_page(page)

                    # Save to memory
                    output_stream = BytesIO()
                    output.write(output_stream)
                    output_stream.seek(0)

                    # Store in session state
                    st.session_state.pdf_data = output_stream.getvalue()
                    st.session_state.student_name = name.strip()
                    st.session_state.certificate_generated = True

                    # Mark roll as used (except admin)
                    if st.session_state.user_roll != ADMIN_ROLL:
                        new_row = pd.DataFrame([{"roll": st.session_state.user_roll}])
                        used_rolls_updated = pd.concat([used_rolls, new_row], ignore_index=True)
                        used_rolls_updated.to_csv(USED_ROLLS_FILE, index=False)

                    st.success("🎉 Certificate generated successfully!")

            except Exception as e:
                st.error(f"❌ Error generating certificate: {str(e)}")

    # Display download button if certificate is generated
    if st.session_state.certificate_generated and st.session_state.pdf_data:
        st.divider()
        st.subheader("📥 Download Your Certificate")

        st.download_button(
            label="📥 Download Certificate PDF",
            data=st.session_state.pdf_data,
            file_name=f"Certificate_{st.session_state.student_name.replace(' ', '_')}.pdf",
            mime="application/pdf",
            type="primary"
        )

        if st.session_state.user_roll == ADMIN_ROLL:
            st.info("ℹ️ Admin mode: You can generate multiple certificates without restrictions.")

            # Option to generate another certificate
            if st.button("🔄 Generate Another Certificate"):
                st.session_state.certificate_generated = False
                st.session_state.pdf_data = None
                st.session_state.student_name = ""
                st.rerun()
