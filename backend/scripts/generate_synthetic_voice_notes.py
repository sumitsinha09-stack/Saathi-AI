#!/usr/bin/env python3
"""
Saathi AI Synthetic Voice Note Dataset Generator
Generates >= 20 synthetic audio fixtures covering:
- English (4)
- Hindi (4)
- Tamil (4)
- Accents (2)
- Background Noise (2)
- Silent Audio (1 negative)
- Too Long Audio >120s (1 negative)
- Malformed / Unsupported Audio (2 negative)

Produces WAV audio files and manifest.json in backend/tests/fixtures/voice_notes/
"""

import json
import os
import struct
import subprocess
import tempfile
import wave
import numpy as np

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests",
    "fixtures",
    "voice_notes",
)


DATASET_SPEC = [
    # 1. English (4 samples)
    {
        "id": "en_01",
        "filename": "en_01_bank_impersonation.wav",
        "category": "English speech",
        "voice": "Aman",
        "language": "en",
        "is_valid": True,
        "scenario": "Fake bank representative asking for card details and OTP",
        "text": (
            "Hello, this is officer Rajesh Sharma calling from Apex Union Bank security division. "
            "Your debit card ending in 4 8 2 1 has been temporarily locked due to a suspicious charge "
            "of 15000 rupees. To unblock your account immediately, please verify your identity by "
            "sharing the 6 digit one-time password 8 3 9 1 0 4 sent to your mobile phone right now."
        ),
        "ground_truth": {
            "incident_type": "Bank Impersonation",
            "reported_entity": "Apex Union Bank",
            "incident_date": None,
            "financial_loss": 15000.0,
            "phone_number": None,
            "sensitive_values": ["839104", "4821"],
        },
    },
    {
        "id": "en_02",
        "filename": "en_02_kyc_freeze.wav",
        "category": "English speech",
        "voice": "Rishi",
        "language": "en",
        "is_valid": True,
        "scenario": "Fraudulent electricity bill KYC warning",
        "text": (
            "Dear consumer, your electricity power supply will be disconnected tonight at 9 PM "
            "because your previous month bill of 3250 rupees was not updated on the Urja Power portal. "
            "Immediately contact our helpline officer Mr Verma on phone number 9876543210 "
            "to complete your KYC verification."
        ),
        "ground_truth": {
            "incident_type": "Electricity KYC Fraud",
            "reported_entity": "Urja Power",
            "incident_date": None,
            "financial_loss": 3250.0,
            "phone_number": "9876543210",
            "sensitive_values": [],
        },
    },
    {
        "id": "en_03",
        "filename": "en_03_lottery_scam.wav",
        "category": "English speech",
        "voice": "Samantha",
        "language": "en",
        "is_valid": True,
        "scenario": "Fake lottery prize winning notification",
        "text": (
            "Congratulations! Your mobile number has won a cash prize of 25 lakh rupees in the "
            "National Consumer Lucky Draw 2026. To claim your prize money, you must transfer a "
            "refundable government tax fee of 12500 rupees to our designated bank account within two hours."
        ),
        "ground_truth": {
            "incident_type": "Lottery Scam",
            "reported_entity": "National Consumer Lucky Draw",
            "incident_date": "2026",
            "financial_loss": 12500.0,
            "phone_number": None,
            "sensitive_values": [],
        },
    },
    {
        "id": "en_04",
        "filename": "en_04_courier_fraud.wav",
        "category": "English speech",
        "voice": "Daniel",
        "language": "en",
        "is_valid": True,
        "scenario": "Fake courier customs drug parcel scam",
        "text": (
            "Good day, this is automated dispatch from SpeedPost Express customs hub in Mumbai. "
            "A suspicious parcel containing illegal contraband under your name has been intercepted. "
            "An arrest warrant has been issued by Mumbai cyber crime branch unless you clear clearance charges."
        ),
        "ground_truth": {
            "incident_type": "Courier Customs Fraud",
            "reported_entity": "SpeedPost Express",
            "incident_date": None,
            "financial_loss": None,
            "phone_number": None,
            "sensitive_values": [],
        },
    },

    # 2. Hindi (4 samples)
    {
        "id": "hi_01",
        "filename": "hi_01_bank_otp.wav",
        "category": "Hindi speech",
        "voice": "Lekha",
        "language": "hi",
        "is_valid": True,
        "scenario": "Fake bank manager demanding OTP in Hindi",
        "text": (
            "नमस्ते, मैं भारत सेवा बैंक के ग्राहक सेवा विभाग से बात कर रहा हूँ। "
            "आपके खाते से दस हज़ार रुपये का अनधिकृत ऑनलाइन लेन-देन करने का प्रयास किया गया है। "
            "खाते को तुरंत सुरक्षित करने के लिए अपने मोबाइल पर आया हुआ छह अंकों का ओटीपी 5 2 9 4 1 8 बताएं।"
        ),
        "ground_truth": {
            "incident_type": "Bank Fraud",
            "reported_entity": "भारत सेवा बैंक",
            "incident_date": None,
            "financial_loss": 10000.0,
            "phone_number": None,
            "sensitive_values": ["529418"],
        },
    },
    {
        "id": "hi_02",
        "filename": "hi_02_electricity_bill.wav",
        "category": "Hindi speech",
        "voice": "Lekha",
        "language": "hi",
        "is_valid": True,
        "scenario": "Electricity bill disconnection threat in Hindi",
        "text": (
            "प्रिय उपभोक्ता, आपका बिजली बिल बकाया है। यदि आज शाम तक चार हज़ार पांच सौ रुपये का भुगतान "
            "नहीं किया गया, तो विद्युत निगम द्वारा आपका कनेक्शन तुरंत काट दिया जाएगा। "
            "सहायता के लिए हमारे हेल्पलाइन नंबर 9811223344 पर संपर्क करें।"
        ),
        "ground_truth": {
            "incident_type": "Electricity Scam",
            "reported_entity": "विद्युत निगम",
            "incident_date": None,
            "financial_loss": 4500.0,
            "phone_number": "9811223344",
            "sensitive_values": [],
        },
    },
    {
        "id": "hi_03",
        "filename": "hi_03_instant_loan.wav",
        "category": "Hindi speech",
        "voice": "Lekha",
        "language": "hi",
        "is_valid": True,
        "scenario": "Instant fake loan app processing fee extortion",
        "text": (
            "बधाई हो, धनवर्षा फाइनेंस द्वारा आपका पचास हज़ार रुपये का पर्सनल लोन बिना किसी दस्तावेज के स्वीकृत कर दिया गया है। "
            "लोन की राशि तुरंत अपने बैंक खाते में प्राप्त करने के लिए नौ सौ निन्यानवे रुपये प्रोसेसिंग फीस यूपीआई द्वारा ट्रांसफर करें।"
        ),
        "ground_truth": {
            "incident_type": "Loan App Fraud",
            "reported_entity": "धनवर्षा फाइनेंस",
            "incident_date": None,
            "financial_loss": 999.0,
            "phone_number": None,
            "sensitive_values": [],
        },
    },
    {
        "id": "hi_04",
        "filename": "hi_04_part_time_job.wav",
        "category": "Hindi speech",
        "voice": "Lekha",
        "language": "hi",
        "is_valid": True,
        "scenario": "Work from home YouTube like scam in Hindi",
        "text": (
            "नमस्ते, स्टार मीडिया मार्केटिंग से अंशकालिक नौकरी का सुनहरा अवसर। "
            "प्रतिदिन यूट्यूब वीडियो लाइक करके तीन हज़ार रुपये कमाएं। "
            "शुरुआती पंजीकरण के लिए टेलीग्राम ग्रुप से जुड़ें और दो हज़ार रुपये का अग्रिम सुरक्षा शुल्क जमा करें।"
        ),
        "ground_truth": {
            "incident_type": "Job Scam",
            "reported_entity": "स्टार मीडिया मार्केटिंग",
            "incident_date": None,
            "financial_loss": 2000.0,
            "phone_number": None,
            "sensitive_values": [],
        },
    },

    # 3. Tamil (4 samples)
    {
        "id": "ta_01",
        "filename": "ta_01_bank_block.wav",
        "category": "Tamil speech",
        "voice": "Vani",
        "language": "ta",
        "is_valid": True,
        "scenario": "Bank debit card blocked scam in Tamil",
        "text": (
            "வணக்கம், நான் பாரத் வங்கி மேலாளர் பேசுகிறேன். உங்கள் ஏடிஎம் கார்டு முடக்கப்பட்டுள்ளது. "
            "மீண்டும் கார்டை இயக்க உங்கள் கார்டு எண் மற்றும் மொபைலுக்கு வந்த ஓடிபி எண்ணை உடனடியாக தெரிவிக்கவும்."
        ),
        "ground_truth": {
            "incident_type": "Bank Card Fraud",
            "reported_entity": "பாரத் வங்கி",
            "incident_date": None,
            "financial_loss": None,
            "phone_number": None,
            "sensitive_values": [],
        },
    },
    {
        "id": "ta_02",
        "filename": "ta_02_kyc_warning.wav",
        "category": "Tamil speech",
        "voice": "Vani",
        "language": "ta",
        "is_valid": True,
        "scenario": "SIM card KYC suspension threat in Tamil",
        "text": (
            "அன்பார்ந்த வாடிக்கையாளரே, உங்கள் சிம் கார்டு ஆவண சரிபார்ப்பு நிலுவையில் உள்ளது. "
            "இன்று மாலைக்குள் கேஒய்சி முடிக்காவிட்டால் சேவை முடக்கப்படும். உதவிக்கு உடனே அழையுங்கள்."
        ),
        "ground_truth": {
            "incident_type": "SIM KYC Scam",
            "reported_entity": None,
            "incident_date": None,
            "financial_loss": None,
            "phone_number": None,
            "sensitive_values": [],
        },
    },
    {
        "id": "ta_03",
        "filename": "ta_03_customs_parcel.wav",
        "category": "Tamil speech",
        "voice": "Vani",
        "language": "ta",
        "is_valid": True,
        "scenario": "Customs courier parcel narcotics scam in Tamil",
        "text": (
            "வணக்கம், டெல்லி சுங்கத்துறை அலுவலகத்திலிருந்து பேசுகிறோம். உங்கள் பெயரில் வந்துள்ள பார்சலில் "
            "சட்டவிரோத பொருட்கள் கைப்பற்றப்பட்டுள்ளன. கைது நடவடிக்கையை தவிர்க்க அபராதம் செலுத்துங்கள்."
        ),
        "ground_truth": {
            "incident_type": "Customs Parcel Fraud",
            "reported_entity": "டெல்லி சுங்கத்துறை",
            "incident_date": None,
            "financial_loss": None,
            "phone_number": None,
            "sensitive_values": [],
        },
    },
    {
        "id": "ta_04",
        "filename": "ta_04_prize_scam.wav",
        "category": "Tamil speech",
        "voice": "Vani",
        "language": "ta",
        "is_valid": True,
        "scenario": "Lucky bumper prize draw scam in Tamil",
        "text": (
            "வாழ்த்துகள்! எங்கள் மெகா பம்பர் பரிசில் உங்களுக்கு ஐந்து லட்சம் ரூபாய் பரிசு கிடைத்துள்ளது. "
            "பரிசு தொகையை பெற உடனடியாக பத்தாயிரம் ரூபாய் பதிவுக் கட்டணம் செலுத்த வேண்டும்."
        ),
        "ground_truth": {
            "incident_type": "Lottery Fraud",
            "reported_entity": None,
            "incident_date": None,
            "financial_loss": 10000.0,
            "phone_number": None,
            "sensitive_values": [],
        },
    },

    # 4. Accent Variation (2 samples)
    {
        "id": "accent_01",
        "filename": "accent_01_indian_english_speed.wav",
        "category": "Accent variation",
        "voice": "Tara",
        "language": "en",
        "is_valid": True,
        "scenario": "Fast-paced Indian English tech support scam",
        "text": (
            "Hello sir, I am calling urgently from Global Cyber Shield Helpdesk. "
            "We have detected a trojan malware virus infected on your personal laptop. "
            "Please download AnyDesk remote software quickly and pay 499 rupees registration."
        ),
        "ground_truth": {
            "incident_type": "Tech Support Scam",
            "reported_entity": "Global Cyber Shield Helpdesk",
            "incident_date": None,
            "financial_loss": 499.0,
            "phone_number": None,
            "sensitive_values": [],
        },
    },
    {
        "id": "accent_02",
        "filename": "accent_02_fast_hinglish.wav",
        "category": "Accent variation",
        "voice": "Aman",
        "language": "en",
        "is_valid": True,
        "scenario": "Conversational Hinglish credit card reward points scam",
        "text": (
            "Hello sir, your credit card reward points are expiring today. "
            "You have total 8500 points worth 4250 rupees in cash. "
            "To redeem directly into your bank account, please confirm the secret OTP sent on your phone."
        ),
        "ground_truth": {
            "incident_type": "Reward Points Scam",
            "reported_entity": None,
            "incident_date": None,
            "financial_loss": 4250.0,
            "phone_number": None,
            "sensitive_values": [],
        },
    },

    # 5. Background Noise (2 samples)
    {
        "id": "noise_01",
        "filename": "noise_01_traffic_english.wav",
        "category": "Background noise",
        "voice": "Rishi",
        "language": "en",
        "is_valid": True,
        "scenario": "English fraudulent call mixed with realistic street traffic noise",
        "text": (
            "Urgent notice from Axis Federal Credit office. A pending payment of 8400 rupees is overdue. "
            "Please clear this balance immediately to avoid court summons."
        ),
        "add_noise": True,
        "ground_truth": {
            "incident_type": "Credit Payment Scam",
            "reported_entity": "Axis Federal Credit",
            "incident_date": None,
            "financial_loss": 8400.0,
            "phone_number": None,
            "sensitive_values": [],
        },
    },
    {
        "id": "noise_02",
        "filename": "noise_02_cafe_hindi.wav",
        "category": "Background noise",
        "voice": "Lekha",
        "language": "hi",
        "is_valid": True,
        "scenario": "Hindi fraud call mixed with cafe ambient chatter noise",
        "text": (
            "नमस्ते, आपके खाते में सात हज़ार रुपये का कैशबैक आया है। "
            "इसे क्लेम करने के लिए अपना यूपीआई पिन दर्ज करें।"
        ),
        "add_noise": True,
        "ground_truth": {
            "incident_type": "Cashback Scam",
            "reported_entity": None,
            "incident_date": None,
            "financial_loss": 7000.0,
            "phone_number": None,
            "sensitive_values": [],
        },
    },

    # 6. Empty / Silent Audio (1 negative sample)
    {
        "id": "neg_01",
        "filename": "neg_01_silent.wav",
        "category": "Empty or silent audio",
        "is_valid": False,
        "scenario": "Empty/silent 2-second audio with zero samples",
        "expected_rejection": "No usable audio samples or zero amplitude detected",
        "special_type": "silent",
    },

    # 7. Excessively Long Audio >120s (1 negative sample)
    {
        "id": "neg_02",
        "filename": "neg_02_too_long.wav",
        "category": "Excessively long audio",
        "is_valid": False,
        "scenario": "Synthetic audio exceeding maximum permitted duration (125 seconds)",
        "expected_rejection": "Audio duration exceeds maximum limit of 120 seconds",
        "special_type": "too_long",
    },

    # 8. Unsupported / Malformed Audio (2 negative samples)
    {
        "id": "neg_03",
        "filename": "neg_03_corrupted_header.wav",
        "category": "Unsupported or malformed audio",
        "is_valid": False,
        "scenario": "Corrupted WAV container with mutilated byte chunks",
        "expected_rejection": "Audio stream decoding failed or container is malformed",
        "special_type": "corrupted",
    },
    {
        "id": "neg_04",
        "filename": "neg_04_bad_codec.wav",
        "category": "Unsupported or malformed audio",
        "is_valid": False,
        "scenario": "Text / random binary payload disguised as audio",
        "expected_rejection": "Audio format validation failed; unsupported header or codec",
        "special_type": "bad_codec",
    },
]


def generate_tts_wav(text: str, voice: str, out_wav_path: str, add_noise: bool = False) -> None:
    """Uses macOS `say` and `afconvert` to synthesize standard 16kHz WAV audio."""
    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp_aiff:
        tmp_aiff_path = tmp_aiff.name

    try:
        # Run say command
        subprocess.run(["say", "-v", voice, "-o", tmp_aiff_path, text], check=True)
        # Convert to standard 16kHz mono 16-bit PCM WAV
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", tmp_aiff_path, out_wav_path],
            check=True,
        )

        # Optionally add background noise
        if add_noise:
            with wave.open(out_wav_path, "rb") as wf:
                params = wf.getparams()
                nframes = params.nframes
                raw_bytes = wf.readframes(nframes)
                samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)

            # Generate synthetic Gaussian background noise with ~15 dB SNR
            signal_power = np.mean(samples**2)
            noise_power = signal_power / 30.0  # ~15 dB SNR
            noise = np.random.normal(0, np.sqrt(noise_power), len(samples))
            noisy_samples = np.clip(samples + noise, -32768, 32767).astype(np.int16)

            with wave.open(out_wav_path, "wb") as wf:
                wf.setparams(params)
                wf.writeframes(noisy_samples.tobytes())

    finally:
        if os.path.exists(tmp_aiff_path):
            os.remove(tmp_aiff_path)


def generate_silent_wav(out_wav_path: str, duration_sec: float = 2.0, sample_rate: int = 16000) -> None:
    """Creates a WAV file of pure digital silence (zero samples)."""
    n_samples = int(duration_sec * sample_rate)
    silence = np.zeros(n_samples, dtype=np.int16)
    with wave.open(out_wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(silence.tobytes())


def generate_too_long_wav(out_wav_path: str, duration_sec: float = 125.0, sample_rate: int = 8000) -> None:
    """Creates a lightweight WAV file that exceeds the 120-second duration limit."""
    n_samples = int(duration_sec * sample_rate)
    # Generate low-amplitude gentle tone to represent valid audio stream exceeding length
    t = np.linspace(0, duration_sec, n_samples, endpoint=False)
    tone = (np.sin(2 * np.pi * 440 * t) * 1000).astype(np.int16)
    with wave.open(out_wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(tone.tobytes())


def generate_corrupted_wav(out_wav_path: str) -> None:
    """Creates a broken WAV file with corrupted internal chunks."""
    header = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\xff\xff\xff\xff"
    garbage = b"\x00\xff\xde\xad\xbe\xef\x00\x11" * 16
    with open(out_wav_path, "wb") as f:
        f.write(header + garbage)


def generate_bad_codec_file(out_wav_path: str) -> None:
    """Creates a non-audio file posing as a WAV file."""
    with open(out_wav_path, "wb") as f:
        f.write(b"NOT_A_VALID_AUDIO_FILE_JUST_RANDOM_TEXT_AND_BYTES\x00\x01\x02\x03\x04\x05")


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    manifest = []

    print(f"Generating synthetic voice note dataset in: {OUTPUT_DIR}")

    for idx, item in enumerate(DATASET_SPEC, 1):
        out_path = os.path.join(OUTPUT_DIR, item["filename"])
        spec_type = item.get("special_type")

        print(f"[{idx:02d}/{len(DATASET_SPEC):02d}] Generating {item['filename']} ({item['category']})...")

        if spec_type == "silent":
            generate_silent_wav(out_path, duration_sec=2.0)
        elif spec_type == "too_long":
            generate_too_long_wav(out_path, duration_sec=125.0)
        elif spec_type == "corrupted":
            generate_corrupted_wav(out_path)
        elif spec_type == "bad_codec":
            generate_bad_codec_file(out_path)
        else:
            generate_tts_wav(
                text=item["text"],
                voice=item["voice"],
                out_wav_path=out_path,
                add_noise=item.get("add_noise", False),
            )

        # Record file size
        file_size = os.path.getsize(out_path) if os.path.exists(out_path) else 0

        entry = {
            "id": item["id"],
            "filename": item["filename"],
            "category": item["category"],
            "is_valid": item["is_valid"],
            "language": item.get("language"),
            "voice": item.get("voice"),
            "scenario": item["scenario"],
            "file_size_bytes": file_size,
            "reference_transcript": item.get("text"),
            "ground_truth": item.get("ground_truth"),
            "expected_rejection": item.get("expected_rejection"),
        }
        manifest.append(entry)

    # Save manifest.json
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nSuccessfully generated {len(manifest)} test cases.")
    print(f"Manifest written to: {manifest_path}")


if __name__ == "__main__":
    main()
