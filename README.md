# Judicom
VoiP Pproject For Memory Care Patients - simplified /safe telephone interface with family photo frame functionality

![Concept Photo](<img/Judicom 2.0 Family Video Phone Concept.png>)

Judicom is an open initiative to build a fully customizable specialty audio / video conferencing device
specially tailored for use by elderly patients dealing with degraded memory.  It has an extremely simple 
user interface (two buttons), a familiar "90s style landline phone" design aesthetic, and a touch sensitive 
HDMI interface that displays family photos (along with relationship descriptions), time/date, and upcoming 
events.

One of its design goals is that it should operate in environments where the only requirement for the phone 
device is a working wifi signal of adequate bandwidth.  A back office PBX (Asterisk) is connected via Tailscale 
and that PBX is interfaced securely to VoIP.ms, where a DID number can be attached to the account, giving 
the device an external telephone number for a monthly small fee.  The back office server also hosts a directory 
of photos and associated metadata that helps to remind the patient of who each picture is, their relationship 
to the patient (your daughter, your husband, your sister, etc.)

Another design goal is to only allow incoming calls from a white list of telephone numbers that can easily be 
changed on the PBX server.  Outgoing calls can only be initiated from the two physical buttons (with 
embedded photographs), limiting the opportunity for confusion.

The device may eventually support video conferencing as well, but this is a secondary design goal for now.

## Hardware

The hardware enclosure is 3D modeled using FreeCAD.  The phone itself is built around a Raspberry Pi 3b+, 
a small 4 ohm speaker for ringtone, and a Merlin style handset with appropriate hardware interfacing to make 
the handset appear as a USB audio device to the SBC (the Pi).  The touch screen is a 7 inch HDMI screen (HS-007) 
from Head Sun, though with appropriate enclosure modification any HDMI touch screen could work.  Touch screen 
functionality isn't strictly necessary, and for now any use of it will be secondary or supportive rather than 
required.

## Software

The Raspberry Pi on the device is run without a desktop, and graphics are drawn directly using PyGame.  PBX 
software is Asterisk, and the device registers itself with Asterisk via Baresip once it can see it 
through the Tailscale network.  PBX/NAS installation is handled via a shell script that makes sure all 
dependencies are present and walks the installer through establishing their VoIP.ms account and getting it 
configured.

## Operation

When the device is in operation with a wifi connection, it periodically pings its PBX to make sure it has 
the necessary connectivity.  Assuming it does, it first checks its local directory of photos and rsyncs 
them from the PBX server to make sure they are up to date. Then it goes into "photo frame" mode.  In photo
frame mode, it randomly selects a photo and displays it on the screen along with the associated meta data 
for that photo for about 30 seconds.  Every fifth image, it switches to an info screen where it depicts the 
current date, current time, current weather, and next event with a count down (birth dates, holidays, etc.)

When the handset is lifted from its cradle, the phone switches to "call mode."  In call mode, the HDMI screen 
shows two arrows pointing down to the phone's two physical buttons, and the handset speaker plays a dialtone 
sound.  Each button is configured to dial a loved one, and a photograph of that loved one can be inserted into 
the button frame.  When the patient depresses one of the buttons, the PBX makes an outbound call to one of the 
loved ones, and the HDMI screen shows "Calling _____..." Assuming the other party picks up, the device 
negotiates with the PBX to route audio back and forth to VoIP.ms.  If the other party does not pick up within 
30 seconds, the HDMI screen changes to "No answer." which remains on the screen for 10 seconds.  
At the end of the 10 seconds, if the handset is still held off the cradle, the phone returns to "call mode" 
where it depicts the two arrows again.  If the handset has been returned to the cradle, the device goes back 
into "photo frame" mode. 

The device has one additional mode, "Receiving mode."  In this mode, when an external party calls the DID 
number of the device (provided by VoIP.ms), the PBX first checks to make sure the calling number is on the 
whitelist. If the number is not on the whitelist, a message is played back to the caller saying "You have 
reached a number that is protected for the safety of a patient.  If you would like to be able to contact 
this patient, please call 555-555-5555, leave you name, number, and relationship to the patient, and within 
a few days, at the patient's family's discretion you can be added to her list of contacts."


If the number is on the white list, the PBX routes the call to the Judicom device via Tailscale/SIP. The 
internal speaker of the Judicom device rings with a traditional ringtone, and the HDMI screen changes to 
"Incoming call from _____ (relationship)" and the phone waits for the handset to be picked up. If it is 
picked up before the third party hangs up, the PBX negotiates the audio conversation, and the HDMI screen 
changes to "Speaking with _______ (relationship)".  When the call ends (either because the handset was hung up 
or because the third party terminated the call), the HDMI screen changes to "Call just ended 
with _____ (relationship)" and remains on the screen for 10 seconds.  Then the phone returns to "photo frame" 
mode.

If at any time the phone detects that the handset has been lifted from the cradle, but nothing has happened 
(in other words, no SIP connection is active), the HDMI screen changes to yellow and displays "Please put the 
handset back on the phone."
