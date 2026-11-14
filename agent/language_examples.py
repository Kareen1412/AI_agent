"""Examples for language recognition and intent interpretation; not hardcoded replies."""

LANGUAGE_EXAMPLES = """
Customer language examples (understand intent, do not copy responses literally):
- English: 'I want 4 red velvet cookies for next Wednesday.' -> add 4 red_velvet; ask filling.
- Lebanese Arabic: 'بدي ٣ كيندر و٢ لوتس لبكرا' -> 3 kinder + 2 lotus, tomorrow.
- Arabizi: 'bade 3 kinder w 2 lotus la bokra' -> 3 kinder + 2 lotus, tomorrow.
- Arabizi: 'baddi 4 red velvet, 2 cream cheese w 2 white chocolate' -> TWO item lines, 2 of each filling.
- Mixed: 'marhaba can I get 5 nutella la jem3a?' -> 5 nutella, Friday (clarify which Friday if needed).
- Change: 'la2 khalliyon 6 kinder mesh 3' -> REPLACE previous kinder quantity with 6; don't add 6.
- Change: 'zid 2 lotus' -> ADD two lotus cookies to current order.
- Removal: 'shil el nutella' -> REMOVE nutella line.
- Date: 'bade yehon l esbou3 l jeye' -> next week, no exact delivery date; ask which day.
- Question: 'adde l kinder?' -> menu price question, not an order.
- Human: 'fini ehke ma3 l owner?' -> request human assistance.
- Approval: 'eh akid' or 'yes confirm' -> approval ONLY if a current validated quote was shown and nothing changed afterward.
- Ambiguous: '3 red velvet' -> ask whether cream_cheese or white_chocolate.
- Phone: WhatsApp customer ID is available from transport, so do not ask for phone again when already supplied.
Use natural Lebanese Arabizi when the customer uses Arabizi; don't switch to formal Arabic unnecessarily.
"""
