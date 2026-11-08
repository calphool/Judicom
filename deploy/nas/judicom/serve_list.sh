#!/bin/sh
# What the Judicom's sync key may read on the NAS, and nothing else.  Its line in /home/pi/.ssh/authorized_keys is
#     restrict,command="/home/pi/judicom/serve_list.sh" ssh-ed25519 ... judicom-contacts-sync
# The Judicom asks for "contacts" (also when it asks for nothing), "events", "verses", "jokes", "people-list" or "people"; anything else
# is refused.  "people-list" is the sha256 and name of each picture in /home/pi/judicom/people (.png .jpg .jpeg, under 5 MB,
# top level only); "people" is those same pictures as one tar file (the Judicom asks for it only when the list has changed).
PEOPLE=/home/pi/judicom/people
pictures() {   # the people pictures, NUL-separated, as ./name
  find . -maxdepth 1 -type f ! -name '.*' \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) -size -5242881c -print0
}
case "${SSH_ORIGINAL_COMMAND:-contacts}" in
  contacts)    exec cat /home/pi/judicom/contacts.txt ;;
  events)      [ -f /home/pi/judicom/events.txt ] && exec cat /home/pi/judicom/events.txt
               exit 0 ;;
  verses)      [ -f /home/pi/judicom/verses.txt ] && exec cat /home/pi/judicom/verses.txt
               exit 0 ;;
  jokes)       [ -f /home/pi/judicom/jokes.txt ] && exec cat /home/pi/judicom/jokes.txt
               exit 0 ;;
  people-list) cd "$PEOPLE" 2>/dev/null || exit 0
               pictures | xargs -0r sha256sum ;;
  people)      cd "$PEOPLE" 2>/dev/null || exit 0
               pictures | tar --null -T - -cf - ;;
  *)           echo "serve_list: only 'contacts', 'events', 'verses', 'jokes', 'people-list' or 'people' may be asked for" >&2
               exit 1 ;;
esac
