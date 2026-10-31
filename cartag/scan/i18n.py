from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

Language = Literal["en", "ur"]
LANGUAGES: tuple[Language, ...] = ("en", "ur")


@dataclass(frozen=True)
class Strings:
    dir: Literal["ltr", "rtl"]
    html_lang: str
    switch_label: str
    switch_to: Language
    active_title: str
    active_subtitle: str
    owner: str
    call: str
    whatsapp: str
    whatsapp_message: str
    emergency_title: str
    blood_group: str
    emergency_contact: str
    call_emergency: str
    emergency_note: str
    not_active_title: str
    not_active_body: str
    activate: str
    turned_off_title: str
    turned_off_body: str
    retired_title: str
    retired_body: str
    not_found_title: str
    not_found_body: str
    privacy_note: str
    powered_by: str
    relation: Callable[[str, str | None], str]


STRINGS: dict[Language, Strings] = {
    "en": Strings(
        dir="ltr",
        html_lang="en",
        switch_label="اردو",
        switch_to="ur",
        active_title="Contact the owner",
        active_subtitle="The owner of this CARTAG can be reached with the buttons below.",
        owner="Owner",
        call="Call Owner",
        whatsapp="WhatsApp Owner",
        whatsapp_message="Hello, I scanned your CARTAG.",
        emergency_title="Emergency information",
        blood_group="Blood group",
        emergency_contact="Emergency contact",
        call_emergency="Call emergency contact",
        emergency_note="The owner added these details. Please check them before you use them.",
        not_active_title="This CARTAG is not active yet",
        not_active_body="If you bought this tag, activate it to start using it.",
        activate="Activate this tag",
        turned_off_title="This tag is turned off",
        turned_off_body="The owner has turned this tag off for now.",
        retired_title="This tag is retired",
        retired_body="This tag has been stopped for good and cannot be used.",
        not_found_title="Tag not found",
        not_found_body="We could not find this tag. Check that the QR code is not damaged.",
        privacy_note="Please be polite. The owner's details are shown only because they chose to share them.",
        powered_by="Powered by CARTAG",
        relation=lambda name, relationship: f"{name} ({relationship})" if relationship else name,
    ),
    "ur": Strings(
        dir="rtl",
        html_lang="ur",
        switch_label="English",
        switch_to="en",
        active_title="مالک سے رابطہ کریں",
        active_subtitle="اس CARTAG کے مالک سے نیچے دیے گئے بٹنوں سے رابطہ کیا جا سکتا ہے۔",
        owner="مالک",
        call="مالک کو کال کریں",
        whatsapp="مالک کو واٹس ایپ کریں",
        whatsapp_message="السلام علیکم، میں نے آپ کا CARTAG اسکین کیا ہے۔",
        emergency_title="ہنگامی معلومات",
        blood_group="بلڈ گروپ",
        emergency_contact="ہنگامی رابطہ",
        call_emergency="ہنگامی رابطے کو کال کریں",
        emergency_note="یہ تفصیلات مالک نے خود درج کی ہیں۔ استعمال کرنے سے پہلے ان کی تصدیق کر لیں۔",
        not_active_title="یہ CARTAG ابھی فعال نہیں ہوا",
        not_active_body="اگر آپ نے یہ ٹیگ خریدا ہے تو استعمال شروع کرنے کے لیے اسے فعال کریں۔",
        activate="ٹیگ فعال کریں",
        turned_off_title="یہ ٹیگ بند ہے",
        turned_off_body="مالک نے فی الحال اس ٹیگ کو بند کر رکھا ہے۔",
        retired_title="یہ ٹیگ ریٹائر ہو چکا ہے",
        retired_body="اس ٹیگ کو ہمیشہ کے لیے بند کر دیا گیا ہے اور اب یہ استعمال نہیں ہو سکتا۔",
        not_found_title="ٹیگ نہیں ملا",
        not_found_body="ہمیں یہ ٹیگ نہیں ملا۔ دیکھیں کہ QR کوڈ خراب تو نہیں ہے۔",
        privacy_note="براہِ کرم شائستگی سے بات کریں۔ مالک کی تفصیلات صرف اس لیے دکھائی جا رہی ہیں کہ انہوں نے خود شیئر کی ہیں۔",
        powered_by="CARTAG کی جانب سے",
        relation=lambda name, relationship: f"{name} ({relationship})" if relationship else name,
    ),
}
