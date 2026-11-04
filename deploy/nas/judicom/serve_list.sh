#!/bin/sh
# What the Judicom's sync key may read on the NAS, and nothing else.  Its line in /home/pi/.ssh/authorized_keys is
#     restrict,command="/home/pi/judicom/serve_list.sh" ssh-ed25519 ... judicom-contacts-sync
# The Judicom asks for "contacts" (also when it asks for nothing), "events" or "verses"; anything else is refused.
case "${SSH_ORIGINAL_COMMAND:-contacts}" in
  contacts) exec cat /home/pi/judicom/contacts.txt ;;
  events)   [ -f /home/pi/judicom/events.txt ] && exec cat /home/pi/judicom/events.txt
            exit 0 ;;
  verses)   [ -f /home/pi/judicom/verses.txt ] && exec cat /home/pi/judicom/verses.txt
            exit 0 ;;
  *)        echo "serve_list: only 'contacts', 'events' or 'verses' may be asked for" >&2
            exit 1 ;;
esac
