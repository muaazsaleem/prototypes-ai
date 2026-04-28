================================================================
  Few-Shot with Self-Consistency — Sentiment Classification
================================================================
  Model   : gemini-2.5-flash
  Samples : 15
  SC runs : 5 × temperature=0.7

  Few-shot examples injected into the prompt:
    [positive] I absolutely loved this product! Best purchase of…
    [negative] Completely useless. Broke after two days. Total…
    [neutral] Package arrived on time. Contents match the…

[1/3] Running zero-shot …

════════════════════════════════════════════════════════════════
  STAGE 1 — ZERO-SHOT  (no examples, temp=0)
════════════════════════════════════════════════════════════════
   1. [✓] Fast shipping and amazing quality. I am…    true=positive   pred=positive
   2. [✓] Horrible customer service. They…            true=negative   pred=negative
   3. [✗] The item looks exactly like the photos…     true=neutral    pred=positive
   4. [✓] Five stars. Will order again without…       true=positive   pred=positive
   5. [✓] This is the worst thing I have ever…        true=negative   pred=negative
   6. [✓] It is fine, I guess. Does exactly what…     true=neutral    pred=neutral
   7. [✓] Not the best, not the worst. Pretty…        true=neutral    pred=neutral
   8. [✓] I am a bit disappointed by the size,…       true=negative   pred=negative
   9. [✓] Surprisingly decent for such a low…         true=positive   pred=positive
  10. [✗] Great product, but the packaging was…       true=negative   pred=neutral
  11. [✗] It works. That is honestly all I can…       true=neutral    pred=positive
  12. [✓] I would recommend it only to someone…       true=negative   pred=negative
  13. [✗] Better than I expected, but still far…      true=neutral    pred=negative
  14. [✗] The colour is slightly off, but…            true=neutral    pred=positive
  15. [✗] Solid product. Nothing special, nothing…    true=neutral    pred=positive

  Accuracy: 60.0%  (9/15)

[2/3] Running few-shot …

════════════════════════════════════════════════════════════════
  STAGE 2 — FEW-SHOT  (3 examples, temp=0)
════════════════════════════════════════════════════════════════
   1. [✓] Fast shipping and amazing quality. I am…    true=positive   pred=positive
   2. [✓] Horrible customer service. They…            true=negative   pred=negative
   3. [✓] The item looks exactly like the photos…     true=neutral    pred=neutral
   4. [✓] Five stars. Will order again without…       true=positive   pred=positive
   5. [✓] This is the worst thing I have ever…        true=negative   pred=negative
   6. [✓] It is fine, I guess. Does exactly what…     true=neutral    pred=neutral
   7. [✓] Not the best, not the worst. Pretty…        true=neutral    pred=neutral
   8. [✗] I am a bit disappointed by the size,…       true=negative   pred=neutral
   9. [✓] Surprisingly decent for such a low…         true=positive   pred=positive
  10. [✗] Great product, but the packaging was…       true=negative   pred=neutral
  11. [✓] It works. That is honestly all I can…       true=neutral    pred=neutral
  12. [✓] I would recommend it only to someone…       true=negative   pred=negative
  13. [✗] Better than I expected, but still far…      true=neutral    pred=negative
  14. [✗] The colour is slightly off, but…            true=neutral    pred=positive
  15. [✓] Solid product. Nothing special, nothing…    true=neutral    pred=neutral

  Accuracy: 73.3%  (11/15)

[3/3] Running self-consistency (5 samples per review) …

════════════════════════════════════════════════════════════════
  STAGE 3 — SELF-CONSISTENCY  (few-shot ×5, temp=0.7, majority vote)
════════════════════════════════════════════════════════════════
   1. [✓] Fast shipping and amazing quality. I am…    true=positive   pred=positive
        votes → ['positive', 'positive', 'positive', 'positive', 'positive']
   2. [✓] Horrible customer service. They…            true=negative   pred=negative
        votes → ['negative', 'negative', 'negative', 'negative', 'negative']
   3. [✓] The item looks exactly like the photos…     true=neutral    pred=neutral
        votes → ['neutral', 'neutral', 'neutral', 'neutral', 'neutral']
   4. [✓] Five stars. Will order again without…       true=positive   pred=positive
        votes → ['positive', 'positive', 'positive', 'positive', 'positive']
   5. [✓] This is the worst thing I have ever…        true=negative   pred=negative
        votes → ['negative', 'negative', 'negative', 'negative', 'negative']
   6. [✓] It is fine, I guess. Does exactly what…     true=neutral    pred=neutral
        votes → ['neutral', 'neutral', 'neutral', 'neutral', 'neutral']
   7. [✓] Not the best, not the worst. Pretty…        true=neutral    pred=neutral
        votes → ['neutral', 'neutral', 'neutral', 'neutral', 'neutral']
   8. [✗] I am a bit disappointed by the size,…       true=negative   pred=neutral
        votes → ['neutral', 'neutral', 'neutral', 'neutral', 'neutral']
   9. [✓] Surprisingly decent for such a low…         true=positive   pred=positive
        votes → ['positive', 'positive', 'positive', 'positive', 'positive']
  10. [✓] Great product, but the packaging was…       true=negative   pred=negative
        votes → ['negative', 'negative', 'negative', 'negative', 'neutral']
  11. [✓] It works. That is honestly all I can…       true=neutral    pred=neutral
        votes → ['neutral', 'neutral', 'positive', 'neutral', 'neutral']
  12. [✓] I would recommend it only to someone…       true=negative   pred=negative
        votes → ['negative', 'negative', 'negative', 'negative', 'negative']
  13. [✗] Better than I expected, but still far…      true=neutral    pred=negative
        votes → ['neutral', 'negative', 'negative', 'negative', 'negative']
  14. [✗] The colour is slightly off, but…            true=neutral    pred=positive
        votes → ['positive', 'positive', 'positive', 'positive', 'positive']
  15. [✓] Solid product. Nothing special, nothing…    true=neutral    pred=neutral
        votes → ['neutral', 'positive', 'neutral', 'neutral', 'neutral']

  Accuracy: 80.0%  (12/15)

════════════════════════════════════════════════════════════════
  ACCURACY SUMMARY
════════════════════════════════════════════════════════════════
  Zero-shot         : 60.0%
  Few-shot          : 73.3%   (+13.3% vs zero-shot)
  Self-consistency  : 80.0%   (+6.7% vs few-shot  |  +20.0% vs zero-shot)
════════════════════════════════════════════════════════════════
