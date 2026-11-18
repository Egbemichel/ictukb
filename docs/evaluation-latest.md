# Retrieval evaluation

| Metric | Value |
|---|---|
| Questions | 103 |
| Answerable questions with indexed documents (coverage) | 63 of 98 (64.3%) |
| hit@5 on covered questions | 88.9% (target 85%) |
| hit@5 on covered P0 questions | 100.0% (target 95%), 19 of 19 P0 covered |
| Mean reciprocal rank | 86.6% |
| Retrieved correctly and answered with high confidence | 82.1% |
| No-answer correctness | 100.0% |
| Lowest top similarity among answered questions | 0.49820998819968265 |
| Highest top similarity among no-answer questions | 0.6279112782512869 |

## Failures

| Question | Priority | Confidence | Returned documents |
|---|---|---|---|
| PRG-05 | P1 | high | web-international-masters-in-business-administration-imba, web-masters-of-science-msc-in-development-planning-dvp, web-masters-msc-in-applied-statistics-and-demography, about-academic-regulations, people-course-lecturers-files |
| TTB-04 | P1 | low | web-academic-calendar-2026-2027, web-academic-calendar-2026-2027, about-academic-calendar, timetables-classes, programs-curriculum-files |
| PPL-05 | P2 | low | about-contacts, timetables-classes, procedures-complaints, procedures-complaints, web-faculty-of-bms |
| PPL-06 | P2 | high | programs-curriculum-files, web-bachelors-of-science-bsc-in-software-engineering-se, web-bachelors-of-science-bsc-in-software-engineering-se, web-bachelors-of-science-bsc-in-software-engineering-se, web-bachelors-of-science-bsc-in-software-engineering-se |
| MHP-01 | P1 | high | procedures-transcript, procedures-transcript, erp-fee-statement, erp-support, finance-late-payment |
| MHP-02 | P1 | high | procedures-resits, procedures-resits, procedures-resits, procedures-complaints, erp-course-registration |
| MHP-03 | P1 | high | admissions-masters-requirements, web-maters-degree-entry-requirements, finance-late-payment, web-maters-degree-entry-requirements, web-masters-programs |

## Not yet covered (expected documents missing from the index)

ADM-04, ADM-08, PRG-03, PRG-07, PRG-08, PRC-11, FIN-09, ERP-08, CMP-02, CMP-03, CMP-04, CMP-05, CMP-06, CMP-07, CMP-08, CMP-09, TRN-01, TRN-02, TRN-03, CAN-01, CAN-02, CAN-03, CAN-04, PPL-01, PPL-02, PPL-03, STL-01, STL-02, STL-03, STL-04, STL-05, STL-06, MHP-04, VAR-03, VAR-05
