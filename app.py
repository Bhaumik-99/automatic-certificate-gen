import streamlit as st
import pandas as pd
import os     
from pypdf import PdfReader, PdfWriter  
from fpdf import FPDF 
from io import BytesIO 
  
# ===================================
# CONFIGURATION (change filenames / admin roll as needed)
# =================================== 
ADMIN_ROLL = "ADMIN"  # change to your admin roll if needed
TEMPLATE_FILE = "certificate_template.pdf"    
ALLOWED_ROLLS_FILE = "allowed_rolls.csv"  # should contain a column named 'roll' 
USED_ROLLS_FILE = "used_rolls.csv"  # will be created if missing
STUDENT_FONT = "Helvetica"  # FPDF only supports a few built-in fonts

st.set_page_config(page_title="🎓 Certificate Portal", page_icon="🎓", layout="centered") 
st.title("🎓 Student Certificate Portal (Roll-based one-time login)")

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
                    # Create overlay PDF with name
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font(STUDENT_FONT, "B", size=font_size)
                    pdf.set_text_color(0, 0, 0)

                    # Determine the center of the page
                    # Use template's mediabox width for accurate centering
                    temp_reader = PdfReader(open(TEMPLATE_FILE, "rb"))
                    page_width = float(temp_reader.pages[0].mediabox.width)
                    pdf_size = page_width / 2
                    # Position the name (adjust y as needed for your template)
                    y_position = 120
                    pdf.text(pdf_size - pdf.get_string_width(name) / 2, y_position, name.strip())

                    # Save overlay to memory
                    overlay_stream = BytesIO()
                    pdf.output(overlay_stream)
                    overlay_stream.seek(0)
                    overlay_pdf = PdfReader(overlay_stream)

                    # Merge overlay with base certificate
                    existing_pdf = PdfReader(open(TEMPLATE_FILE, "rb"))
                    output = PdfWriter()
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
