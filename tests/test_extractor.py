from app.scraper.extractor import extract_project
from app.scraper.html import parse_html


def test_extracts_nirvana_style_project_details():
    soup = parse_html("""
    <html><h1>Nirvana Aparotelz Live Smart Earn Smarter.</h1>
    <p>1 BHK Luxury Apartment in Neemrana Starting at ₹30 Lakhs Only RERA Approved.</p>
    <p>RERA No. RAJ/P/2017/313, RAJ/P/2017/314, RAJ/P/2017/315</p>
    <p>Registered Office : No 967/968, Chobara, Behind RIICO Industrial Area,
    Tehsil- Neemrana, Dist Alwar, Rajasthan - 301706</p>
    <p>24x7 Security with CCTV Power Backup Internet / Wi-Fi Gym Fire Fighting System Yoga Lounge</p>
    </html>
    """)
    project = extract_project("https://nirvanaaparotelz.com/", soup, "Venetian LDF Projects LLP")

    assert project.city == "Neemrana"
    assert project.state == "Rajasthan"
    assert project.status == "RERA Approved"
    assert project.starting_price == "₹30 Lakhs"
    assert project.rera_number == "RAJ/P/2017/313, RAJ/P/2017/314, RAJ/P/2017/315"
    assert "Gym" in project.amenities


def test_extracts_godrej_alira_unit_sizes():
    soup = parse_html("""
    <html><h1>Godrej Alira</h1>
    <p>Size : 3 BHK - 2500 Sq. Ft.*</p>
    <p>Size : 4 BHK - 3200 Sq. Ft.*</p>
    <p>Starting Price Rs. 6 Cr onwards</p>
    </html>
    """)

    project = extract_project("https://www.luxuryresidences.in/godrej-alira-in-sector-39-gurgaon/", soup, "Godrej Properties")

    assert project.unit_types == ["3 BHK", "4 BHK"]
    assert project.sizes == ["3 BHK - 2500 Sq. Ft", "4 BHK - 3200 Sq. Ft"]
