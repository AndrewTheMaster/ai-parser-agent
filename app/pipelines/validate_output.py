"""Post-lookup validation: confidence floors, empty quotes, status consistency."""

from __future__ import annotations

from app.schemas.term import DictionaryStatus, TermLookupResult


def validate_results(results: list[TermLookupResult]) -> list[TermLookupResult]:
    fixed: list[TermLookupResult] = []
    for r in results:
        defs = [d for d in r.definitions if d.quote and d.quote.strip()]
        status = r.dictionary_status
        if status != DictionaryStatus.NOT_FOUND and not defs:
            status = DictionaryStatus.NOT_FOUND
            r = r.model_copy(
                update={
                    "dictionary_status": status,
                    "definitions": [],
                    "notes": (r.notes + "; empty quotes demoted to NOT_FOUND").strip("; "),
                    "manual_review": True,
                    "confidence": 0.0,
                }
            )
        elif not defs and status != DictionaryStatus.NOT_FOUND:
            r = r.model_copy(update={"definitions": defs})
        else:
            r = r.model_copy(update={"definitions": defs})

        manual = r.manual_review
        if r.dictionary_status == DictionaryStatus.FOUND_COMPONENT:
            manual = True
        if r.confidence < 0.5:
            manual = True
        fixed.append(r.model_copy(update={"manual_review": manual}))
    return fixed
