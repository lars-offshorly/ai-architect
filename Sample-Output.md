{
    "success": true,
    "dashboard": {
        "id": "60781",
        "name": "Generated Dashboard from Insights - 0414260346",
        "url": "/dashboard/60781"
    },
    "widgets": {
        "text": 9,
        "number": 7,
        "bar": 2,
        "hbar": 2,
        "pie": 0,
        "line": 0,
        "scatter": 0,
        "list": 1,
        "combo": 0,
        "embed": 0,
        "total": 21
    },
    "execution_time": "0m 22s",
    "errors": [],
    "debug_payload": {
        "widgets": [
            {
                "id": 1,
                "name": "Dashboard Summary",
                "typeId": 2,
                "order": 0,
                "description": "The report analyzes attendance patterns across departments and job levels, revealing significant deficits that impact workforce efficiency and financial performance. Key findings indicate that certain departments experience the highest absenteeism, necessitating targeted HR interventions and improved data capture for better decision-making.",
                "settings": {
                    "width": 12,
                    "height": 3,
                    "xAxis": 0,
                    "yAxis": 0,
                    "id": 1
                }
            },
            {
                "id": 2,
                "name": "Key Findings",
                "typeId": 2,
                "order": 0,
                "description": "- Of 7,857 attendance records, 4,351 records (55%) contain a recorded deficit, making deficit the most reliable proxy for absenteeism and lost hours. Total deficit was summarized by department and job level for dashboard panels.<br>- Metrics for late, overtime, and undertime are sparsely populated (only 80–91 non-null entries each), so comparisons using these fields are low-confidence unless sample-size thresholds are applied.<br>- Department concentration: five departments account for the largest total deficit volumes and should be prioritized for operational review.",
                "settings": {
                    "width": 12,
                    "height": 3,
                    "xAxis": 0,
                    "yAxis": 3,
                    "id": 2
                }
            },
            {
                "id": 3,
                "name": "Key Insights",
                "typeId": 2,
                "order": 0,
                "description": "- Deficit (absenteeism) is prevalent and concentrated by department<br>- Monthly trend highlights sustained deficits in top departments<br>- 'Absent' status counts reveal operational pressure points<br>- Job-level deficits concentrated in 'Staff' but job-level metadata is incomplete<br>- Lateness measures exist but are too sparse for generalization",
                "settings": {
                    "width": 12,
                    "height": 3,
                    "xAxis": 0,
                    "yAxis": 6,
                    "id": 3
                }
            },
            {
                "id": 4,
                "name": "Recommendations",
                "typeId": 2,
                "order": 0,
                "description": "Top Recommendations:<br>- Launch focused absence-reduction programs in test department name and QA Department Test 1 (highest deficit totals).<br>- Implement a 90-day SLA for requalification and follow-up on employees with repeated deficits (defined as > 5 deficit records in 90 days).<br>- Require consistent capture of late/overtime/undertime metrics in timekeeping systems before using them for cross-department benchmarking.<br><br>Recommended Actions:<br>- Audit and fix time-entry capture for late, overtime, and undertime to reach a minimum operational threshold (≥5 non-null records per group) before using these for comparative decisions.<br>- Start immediate HR interventions in test department name and QA Department Test 1: targeted scheduling reviews, temporary contingency staffing, and manager-led return-to-work plans.<br>- Implement a 90-day deficit-follow-up SLA: employees with more than 5 deficit records in a rolling 90-day window receive a formal review and requalification plan.<br>- Normalize and complete job-level metadata across employee records within 30 days to enable reliable job-level benchmarking.<br>- Add a KPI tile on the finance dashboard showing total deficit hours (rolling 30/90-day), percent of records with deficit (currently 55%), and top 5 departments by deficit share to trigger executive review.",
                "settings": {
                    "width": 12,
                    "height": 3,
                    "xAxis": 0,
                    "yAxis": 9,
                    "id": 4
                }
            },
            {
                "id": 5,
                "name": "Data Context",
                "typeId": 2,
                "order": 0,
                "description": "Source: aggregated attendance summaries (7,857 attendance records). Key metrics: deficit (4,351 non-null), late/overtime/undertime (≈80–91 non-null each), status and date (fully populated). Limitation: employee job-level is recorded in only 1,080 records; lateness/overtime/undertime fields are sparsely populated. All time values were converted from seconds to hours for reporting.",
                "settings": {
                    "width": 12,
                    "height": 3,
                    "xAxis": 0,
                    "yAxis": 12,
                    "id": 5
                }
            },
            {
                "id": 6,
                "name": "Records with Deficit (count)",
                "typeId": 1,
                "order": 0,
                "settings": {
                    "width": 3,
                    "height": 3,
                    "xAxis": 0,
                    "yAxis": 15,
                    "format": "number",
                    "alignment": "center",
                    "decimal": 0,
                    "currency": "$ - USD",
                    "fontFamily": "arial",
                    "fontStyle": "normal",
                    "showTimePeriod": false,
                    "showComparisonRate": false,
                    "id": 6
                },
                "datasets": [
                    {
                        "abbreviation": "NUM",
                        "color": "var(--color-happy-day-1)",
                        "colorType": "theme",
                        "dataSource": "employees",
                        "module": "HR Hub",
                        "name": "Number Dataset",
                        "operation": "count",
                        "order": 1,
                        "filters": {
                            "items": []
                        },
                        "id": 7
                    }
                ],
                "formula": [
                    {
                        "type": "number",
                        "value": "0",
                        "order": 0,
                        "id": 8
                    }
                ]
            },
            {
                "id": 7,
                "name": "Deficit Rate (% of records)",
                "typeId": 1,
                "order": 0,
                "settings": {
                    "width": 3,
                    "height": 3,
                    "xAxis": 3,
                    "yAxis": 15,
                    "format": "number",
                    "alignment": "center",
                    "decimal": 0,
                    "currency": "$ - USD",
                    "fontFamily": "arial",
                    "fontStyle": "normal",
                    "showTimePeriod": false,
                    "showComparisonRate": false,
                    "id": 9
                },
                "datasets": [
                    {
                        "abbreviation": "NUM",
                        "color": "var(--color-happy-day-1)",
                        "colorType": "theme",
                        "dataSource": "employees",
                        "module": "HR Hub",
                        "name": "Number Dataset",
                        "operation": "count",
                        "order": 1,
                        "filters": {
                            "items": []
                        },
                        "id": 10
                    }
                ],
                "formula": [
                    {
                        "type": "number",
                        "value": "0",
                        "order": 0,
                        "id": 11
                    }
                ]
            },
            {
                "id": 8,
                "name": "Requalification SLA (days) — Recommended",
                "typeId": 1,
                "order": 0,
                "settings": {
                    "width": 3,
                    "height": 3,
                    "xAxis": 6,
                    "yAxis": 15,
                    "format": "number",
                    "alignment": "center",
                    "decimal": 0,
                    "currency": "$ - USD",
                    "fontFamily": "arial",
                    "fontStyle": "normal",
                    "showTimePeriod": false,
                    "showComparisonRate": false,
                    "id": 12
                },
                "datasets": [
                    {
                        "abbreviation": "NUM",
                        "color": "var(--color-happy-day-1)",
                        "colorType": "theme",
                        "dataSource": "employees",
                        "module": "HR Hub",
                        "name": "Number Dataset",
                        "operation": "count",
                        "order": 1,
                        "filters": {
                            "items": []
                        },
                        "id": 13
                    }
                ],
                "formula": [
                    {
                        "type": "number",
                        "value": "0",
                        "order": 0,
                        "id": 14
                    }
                ]
            },
            {
                "id": 9,
                "name": "Total Deficit Hours (Rolling 30 Days)",
                "typeId": 1,
                "order": 0,
                "settings": {
                    "width": 3,
                    "height": 3,
                    "xAxis": 9,
                    "yAxis": 15,
                    "format": "number",
                    "alignment": "center",
                    "decimal": 0,
                    "currency": "$ - USD",
                    "fontFamily": "arial",
                    "fontStyle": "normal",
                    "showTimePeriod": false,
                    "showComparisonRate": false,
                    "id": 15
                },
                "datasets": [
                    {
                        "abbreviation": "NUM",
                        "color": "var(--color-happy-day-1)",
                        "colorType": "theme",
                        "dataSource": "employees",
                        "module": "HR Hub",
                        "name": "Number Dataset",
                        "operation": "count",
                        "order": 1,
                        "filters": {
                            "items": []
                        },
                        "id": 16
                    }
                ],
                "formula": [
                    {
                        "type": "number",
                        "value": "0",
                        "order": 0,
                        "id": 17
                    }
                ]
            },
            {
                "id": 10,
                "name": "Total Deficit Hours (Rolling 90 Days)",
                "typeId": 1,
                "order": 0,
                "settings": {
                    "width": 3,
                    "height": 3,
                    "xAxis": 0,
                    "yAxis": 18,
                    "format": "number",
                    "alignment": "center",
                    "decimal": 0,
                    "currency": "$ - USD",
                    "fontFamily": "arial",
                    "fontStyle": "normal",
                    "showTimePeriod": false,
                    "showComparisonRate": false,
                    "id": 18
                },
                "datasets": [
                    {
                        "abbreviation": "NUM",
                        "color": "var(--color-happy-day-1)",
                        "colorType": "theme",
                        "dataSource": "employees",
                        "module": "HR Hub",
                        "name": "Number Dataset",
                        "operation": "count",
                        "order": 1,
                        "filters": {
                            "items": []
                        },
                        "id": 19
                    }
                ],
                "formula": [
                    {
                        "type": "number",
                        "value": "0",
                        "order": 0,
                        "id": 20
                    }
                ]
            },
            {
                "id": 11,
                "name": "Percent of Records with Deficit",
                "typeId": 1,
                "order": 0,
                "settings": {
                    "width": 3,
                    "height": 3,
                    "xAxis": 3,
                    "yAxis": 18,
                    "format": "percentage",
                    "alignment": "center",
                    "decimal": 0,
                    "currency": "$ - USD",
                    "fontFamily": "arial",
                    "fontStyle": "normal",
                    "showTimePeriod": false,
                    "showComparisonRate": false,
                    "id": 21
                },
                "datasets": [
                    {
                        "abbreviation": "NUM",
                        "color": "var(--color-happy-day-1)",
                        "colorType": "theme",
                        "dataSource": "employees",
                        "module": "HR Hub",
                        "name": "Number Dataset",
                        "operation": "count",
                        "order": 1,
                        "filters": {
                            "items": []
                        },
                        "id": 22
                    }
                ],
                "formula": [
                    {
                        "type": "number",
                        "value": "55",
                        "order": 0,
                        "id": 23
                    }
                ]
            },
            {
                "id": 12,
                "name": "Average Deficit per Record in QA Department Test 1",
                "typeId": 1,
                "order": 0,
                "settings": {
                    "width": 3,
                    "height": 3,
                    "xAxis": 6,
                    "yAxis": 18,
                    "format": "number",
                    "alignment": "center",
                    "decimal": 8,
                    "currency": "$ - USD",
                    "fontFamily": "arial",
                    "fontStyle": "normal",
                    "showTimePeriod": false,
                    "showComparisonRate": false,
                    "id": 24
                },
                "datasets": [
                    {
                        "abbreviation": "NUM",
                        "color": "var(--color-happy-day-1)",
                        "colorType": "theme",
                        "dataSource": "employees",
                        "module": "HR Hub",
                        "name": "Number Dataset",
                        "operation": "count",
                        "order": 1,
                        "filters": {
                            "items": []
                        },
                        "id": 25
                    }
                ],
                "formula": [
                    {
                        "type": "number",
                        "value": "7.21",
                        "order": 0,
                        "id": 26
                    }
                ]
            },
            {
                "id": 13,
                "name": "Total Deficit (hours) by Department",
                "typeId": 3,
                "order": 0,
                "repopulateFields": true,
                "settings": {
                    "width": 6,
                    "height": 6,
                    "xAxis": 0,
                    "yAxis": 21,
                    "fontFamily": "arial",
                    "fontStyle": "normal",
                    "format": null,
                    "alignment": null,
                    "showTimePeriod": null,
                    "showComparisonRate": null,
                    "decimal": null,
                    "currency": null,
                    "chartType": "bar",
                    "chartLegendPosition": "top",
                    "chartLegendSymbol": "square",
                    "chartShowDetails": null,
                    "chartXAxisPosition": "bottom",
                    "chartXAxisMinValueType": "auto",
                    "chartXAxisMinValue": 0,
                    "chartXAxisMaxValueType": "auto",
                    "chartXAxisMaxValue": 0,
                    "chartYAxisMinValueType": "auto",
                    "chartYAxisMinValue": 0,
                    "chartYAxisMaxValueType": "auto",
                    "chartYAxisMaxValue": 0,
                    "chartXAxisInterval": 10,
                    "chartYAxisInterval": 10,
                    "listColumnNumber": null,
                    "listColumnWidth": null,
                    "listColumnAuto": false,
                    "listHideColumn": [
                        "value"
                    ],
                    "listColumnFont": ",",
                    "listColumnSize": null,
                    "listColumnFontSize": "center",
                    "listColumnStyle": "visible",
                    "listColumnColorType": "{}",
                    "listColumnColor": null,
                    "listBodyColorType": null,
                    "listBodyColor": null,
                    "listBodyFont": null,
                    "listBodySize": null,
                    "listBodyStyle": null,
                    "listFullTable": true,
                    "chartSeries": [
                        {
                            "name": "department",
                            "colorType": "theme",
                            "color": "var(--color-happy-day-2)",
                            "dashType": "solid",
                            "lineColorType": "theme",
                            "lineColor": "var(--color-happy-day-2)",
                            "thickness": 0,
                            "opacity": 100,
                            "showLabel": true,
                            "sort": "none"
                        }
                    ],
                    "chartYAxisPosition": [
                        {
                            "valueId": 0,
                            "name": "left",
                            "position": "left"
                        }
                    ],
                    "columnFormats": [],
                    "fontSize": "md",
                    "showEvents": null,
                    "showDetails": null,
                    "participants": null,
                    "leaderboardRankingRule": null,
                    "startDate": null,
                    "endDate": null,
                    "isLeaderboardBonusTriggersEnabled": null,
                    "timePeriodFilters": [],
                    "id": 27
                },
                "datasets": [
                    {
                        "abbreviation": "A",
                        "color": "var(--color-mono-700)",
                        "colorType": "theme",
                        "dataSource": "absences",
                        "module": "HR Hub",
                        "name": "Absences",
                        "operation": "sum",
                        "order": 1,
                        "filters": {
                            "items": []
                        },
                        "id": 28
                    }
                ],
                "formula": [],
                "parameters": [
                    {
                        "id": 29,
                        "name": "department",
                        "displayName": "Department",
                        "filterType": "default",
                        "filterId": "department",
                        "fields": [],
                        "fieldTitles": [],
                        "numberMin": null,
                        "numberMax": null,
                        "numberInterval": null,
                        "dateFrom": null,
                        "dateTo": null,
                        "dateInterval": null,
                        "order": 0,
                        "sortType": null
                    }
                ]
            },
            {
                "id": 14,
                "name": "About: Total Deficit (hours) by Department",
                "typeId": 2,
                "order": 0,
                "description": "**Total Deficit (hours) by Department**<br><br>This bar chart illustrates the total deficit hours by department, highlighting areas for potential interventions based on the concentration of absenteeism.",
                "settings": {
                    "width": 6,
                    "height": 6,
                    "xAxis": 6,
                    "yAxis": 21,
                    "id": 30
                }
            },
            {
                "id": 15,
                "name": "Absence count by department",
                "typeId": 3,
                "order": 0,
                "repopulateFields": false,
                "settings": {
                    "width": 6,
                    "height": 6,
                    "xAxis": 0,
                    "yAxis": 27,
                    "fontFamily": "arial",
                    "fontStyle": "normal",
                    "format": null,
                    "alignment": null,
                    "showTimePeriod": null,
                    "showComparisonRate": null,
                    "decimal": null,
                    "currency": null,
                    "chartType": "barHorizontal",
                    "chartLegendPosition": "top",
                    "chartLegendSymbol": "square",
                    "chartShowDetails": null,
                    "chartXAxisPosition": "bottom",
                    "chartXAxisMinValueType": "auto",
                    "chartXAxisMinValue": 0,
                    "chartXAxisMaxValueType": "auto",
                    "chartXAxisMaxValue": 0,
                    "chartYAxisMinValueType": "auto",
                    "chartYAxisMinValue": 0,
                    "chartYAxisMaxValueType": "auto",
                    "chartYAxisMaxValue": 0,
                    "chartXAxisInterval": 10,
                    "chartYAxisInterval": 10,
                    "listColumnNumber": null,
                    "listColumnWidth": null,
                    "listColumnAuto": false,
                    "listHideColumn": [
                        "value"
                    ],
                    "listColumnFont": ",",
                    "listColumnSize": null,
                    "listColumnFontSize": "center",
                    "listColumnStyle": "visible",
                    "listColumnColorType": "{}",
                    "listColumnColor": null,
                    "listBodyColorType": null,
                    "listBodyColor": null,
                    "listBodyFont": null,
                    "listBodySize": null,
                    "listBodyStyle": null,
                    "listFullTable": true,
                    "chartSeries": [
                        {
                            "name": "department",
                            "colorType": "theme",
                            "color": "var(--color-happy-day-2)",
                            "dashType": "solid",
                            "lineColorType": "theme",
                            "lineColor": "var(--color-happy-day-2)",
                            "thickness": 0,
                            "opacity": 100,
                            "showLabel": true,
                            "sort": "none"
                        }
                    ],
                    "chartYAxisPosition": [
                        {
                            "valueId": 0,
                            "name": "left",
                            "position": "left"
                        }
                    ],
                    "columnFormats": [],
                    "fontSize": "md",
                    "showEvents": null,
                    "showDetails": null,
                    "participants": null,
                    "leaderboardRankingRule": null,
                    "startDate": null,
                    "endDate": null,
                    "isLeaderboardBonusTriggersEnabled": null,
                    "timePeriodFilters": [],
                    "id": 31
                },
                "datasets": [
                    {
                        "abbreviation": "A",
                        "color": "var(--color-mono-700)",
                        "colorType": "theme",
                        "dataSource": "absences",
                        "module": "HR Hub",
                        "name": "Absences",
                        "operation": "count",
                        "order": 1,
                        "filters": {
                            "items": []
                        },
                        "id": 32
                    }
                ],
                "formula": [],
                "parameters": [
                    {
                        "id": 33,
                        "name": "department",
                        "displayName": "Department",
                        "filterType": "default",
                        "filterId": "department",
                        "fields": [
                            "Sales",
                            "Marketing",
                            "IT"
                        ],
                        "fieldTitles": [
                            "Sales",
                            "Marketing",
                            "IT"
                        ],
                        "numberMin": null,
                        "numberMax": null,
                        "numberInterval": null,
                        "dateFrom": null,
                        "dateTo": null,
                        "dateInterval": null,
                        "order": 0,
                        "sortType": null
                    }
                ]
            },
            {
                "id": 16,
                "name": "About: Absence count by department",
                "typeId": 2,
                "order": 0,
                "description": "**Absence count by department**<br><br>This horizontal bar chart displays absence counts grouped by department, providing insights into staffing pressures and potential areas for resource reallocation.",
                "settings": {
                    "width": 6,
                    "height": 6,
                    "xAxis": 6,
                    "yAxis": 27,
                    "id": 34
                }
            },
            {
                "id": 17,
                "name": "Deficit by Job Level",
                "typeId": 3,
                "order": 0,
                "repopulateFields": true,
                "settings": {
                    "width": 6,
                    "height": 6,
                    "xAxis": 0,
                    "yAxis": 33,
                    "fontFamily": "arial",
                    "fontStyle": "normal",
                    "format": null,
                    "alignment": null,
                    "showTimePeriod": null,
                    "showComparisonRate": null,
                    "decimal": null,
                    "currency": null,
                    "chartType": "bar",
                    "chartLegendPosition": "top",
                    "chartLegendSymbol": "square",
                    "chartShowDetails": null,
                    "chartXAxisPosition": "bottom",
                    "chartXAxisMinValueType": "auto",
                    "chartXAxisMinValue": 0,
                    "chartXAxisMaxValueType": "auto",
                    "chartXAxisMaxValue": 0,
                    "chartYAxisMinValueType": "auto",
                    "chartYAxisMinValue": 0,
                    "chartYAxisMaxValueType": "auto",
                    "chartYAxisMaxValue": 0,
                    "chartXAxisInterval": 10,
                    "chartYAxisInterval": 10,
                    "listColumnNumber": null,
                    "listColumnWidth": null,
                    "listColumnAuto": false,
                    "listHideColumn": [
                        "value"
                    ],
                    "listColumnFont": ",",
                    "listColumnSize": null,
                    "listColumnFontSize": "center",
                    "listColumnStyle": "visible",
                    "listColumnColorType": "{}",
                    "listColumnColor": null,
                    "listBodyColorType": null,
                    "listBodyColor": null,
                    "listBodyFont": null,
                    "listBodySize": null,
                    "listBodyStyle": null,
                    "listFullTable": true,
                    "chartSeries": [
                        {
                            "name": "department",
                            "colorType": "theme",
                            "color": "var(--color-happy-day-2)",
                            "dashType": "solid",
                            "lineColorType": "theme",
                            "lineColor": "var(--color-happy-day-2)",
                            "thickness": 0,
                            "opacity": 100,
                            "showLabel": true,
                            "sort": "none"
                        }
                    ],
                    "chartYAxisPosition": [
                        {
                            "valueId": 0,
                            "name": "left",
                            "position": "left"
                        }
                    ],
                    "columnFormats": [],
                    "fontSize": "md",
                    "showEvents": null,
                    "showDetails": null,
                    "participants": null,
                    "leaderboardRankingRule": null,
                    "startDate": null,
                    "endDate": null,
                    "isLeaderboardBonusTriggersEnabled": null,
                    "timePeriodFilters": [],
                    "id": 35
                },
                "datasets": [
                    {
                        "abbreviation": "A",
                        "color": "var(--color-mono-700)",
                        "colorType": "theme",
                        "dataSource": "absences",
                        "module": "HR Hub",
                        "name": "Absences",
                        "operation": "count",
                        "order": 1,
                        "filters": {
                            "items": []
                        },
                        "id": 36
                    }
                ],
                "formula": [],
                "parameters": [
                    {
                        "id": 37,
                        "name": "department",
                        "displayName": "Department",
                        "filterType": "default",
                        "filterId": "department",
                        "fields": [],
                        "fieldTitles": [],
                        "numberMin": null,
                        "numberMax": null,
                        "numberInterval": null,
                        "dateFrom": null,
                        "dateTo": null,
                        "dateInterval": null,
                        "order": 0,
                        "sortType": null
                    }
                ]
            },
            {
                "id": 18,
                "name": "About: Deficit by Job Level",
                "typeId": 2,
                "order": 0,
                "description": "**Deficit by Job Level**<br><br>The chart shows the distribution of deficit hours by job level, revealing that 'Staff' roles account for the largest absolute deficit hours, although the data is limited.",
                "settings": {
                    "width": 6,
                    "height": 6,
                    "xAxis": 6,
                    "yAxis": 33,
                    "id": 38
                }
            },
            {
                "id": 19,
                "name": "Late incidents distribution by department",
                "typeId": 3,
                "order": 0,
                "repopulateFields": true,
                "settings": {
                    "width": 6,
                    "height": 6,
                    "xAxis": 0,
                    "yAxis": 39,
                    "fontFamily": "arial",
                    "fontStyle": "normal",
                    "format": null,
                    "alignment": null,
                    "showTimePeriod": null,
                    "showComparisonRate": null,
                    "decimal": null,
                    "currency": null,
                    "chartType": "barHorizontal",
                    "chartLegendPosition": "top",
                    "chartLegendSymbol": "square",
                    "chartShowDetails": null,
                    "chartXAxisPosition": "bottom",
                    "chartXAxisMinValueType": "auto",
                    "chartXAxisMinValue": 0,
                    "chartXAxisMaxValueType": "auto",
                    "chartXAxisMaxValue": 0,
                    "chartYAxisMinValueType": "auto",
                    "chartYAxisMinValue": 0,
                    "chartYAxisMaxValueType": "auto",
                    "chartYAxisMaxValue": 0,
                    "chartXAxisInterval": 10,
                    "chartYAxisInterval": 10,
                    "listColumnNumber": null,
                    "listColumnWidth": null,
                    "listColumnAuto": false,
                    "listHideColumn": [
                        "value"
                    ],
                    "listColumnFont": ",",
                    "listColumnSize": null,
                    "listColumnFontSize": "center",
                    "listColumnStyle": "visible",
                    "listColumnColorType": "{}",
                    "listColumnColor": null,
                    "listBodyColorType": null,
                    "listBodyColor": null,
                    "listBodyFont": null,
                    "listBodySize": null,
                    "listBodyStyle": null,
                    "listFullTable": true,
                    "chartSeries": [
                        {
                            "name": "department",
                            "colorType": "theme",
                            "color": "var(--color-happy-day-2)",
                            "dashType": "solid",
                            "lineColorType": "theme",
                            "lineColor": "var(--color-happy-day-2)",
                            "thickness": 0,
                            "opacity": 100,
                            "showLabel": true,
                            "sort": "none"
                        }
                    ],
                    "chartYAxisPosition": [
                        {
                            "valueId": 0,
                            "name": "left",
                            "position": "left"
                        }
                    ],
                    "columnFormats": [],
                    "fontSize": "md",
                    "showEvents": null,
                    "showDetails": null,
                    "participants": null,
                    "leaderboardRankingRule": null,
                    "startDate": null,
                    "endDate": null,
                    "isLeaderboardBonusTriggersEnabled": null,
                    "timePeriodFilters": [],
                    "id": 39
                },
                "datasets": [
                    {
                        "abbreviation": "L",
                        "color": "var(--color-mono-700)",
                        "colorType": "theme",
                        "dataSource": "late",
                        "module": "HR Hub",
                        "name": "Late",
                        "operation": "count",
                        "order": 1,
                        "filters": {
                            "items": []
                        },
                        "id": 40
                    }
                ],
                "formula": [],
                "parameters": [
                    {
                        "id": 41,
                        "name": "department",
                        "displayName": "Department",
                        "filterType": "default",
                        "filterId": "department",
                        "fields": [],
                        "fieldTitles": [],
                        "numberMin": null,
                        "numberMax": null,
                        "numberInterval": null,
                        "dateFrom": null,
                        "dateTo": null,
                        "dateInterval": null,
                        "order": 0,
                        "sortType": null
                    }
                ]
            },
            {
                "id": 20,
                "name": "About: Late incidents distribution by department",
                "typeId": 2,
                "order": 0,
                "description": "**Late incidents distribution by department**<br><br>This chart presents the count of late incidents grouped by department, but the sparse data limits its reliability for cross-department comparisons.",
                "settings": {
                    "width": 6,
                    "height": 6,
                    "xAxis": 6,
                    "yAxis": 39,
                    "id": 42
                }
            },
            {
                "id": 21,
                "name": "Top Departments to Prioritize (by deficit)",
                "typeId": 4,
                "order": 0,
                "settings": {
                    "width": 6,
                    "height": 3,
                    "xAxis": 0,
                    "yAxis": 45,
                    "alignment": "left",
                    "columnFormats": [],
                    "listBodyColor": "#eff1f3",
                    "listBodyColorType": "theme",
                    "listBodyFont": "arial",
                    "listBodySize": "md",
                    "listBodyStyle": "normal",
                    "listColumnAuto": false,
                    "listColumnColor": "#685d79",
                    "listColumnColorType": "theme",
                    "listColumnFont": "arial",
                    "listColumnFontSize": "md",
                    "listColumnNumber": 2,
                    "listColumnStyle": "normal",
                    "listColumnWidth": 150,
                    "listFullTable": false,
                    "listHideColumn": [],
                    "id": 43
                },
                "datasets": [
                    {
                        "abbreviation": "A",
                        "color": "var(--color-mono-700)",
                        "colorType": "theme",
                        "dataSource": "absences",
                        "module": "HR Hub",
                        "name": "Absences",
                        "operation": "count",
                        "order": 1,
                        "filters": {
                            "items": []
                        },
                        "id": 44
                    }
                ],
                "formula": [],
                "parameters": [
                    {
                        "id": 45,
                        "name": "absentDate",
                        "displayName": "Absent Date",
                        "filterType": "default",
                        "filterId": "absentDate",
                        "fields": [],
                        "fieldTitles": [],
                        "numberMin": null,
                        "numberMax": null,
                        "numberInterval": null,
                        "dateFrom": null,
                        "dateTo": null,
                        "dateInterval": null,
                        "order": 0,
                        "sortType": null
                    },
                    {
                        "id": 46,
                        "name": "employmentName",
                        "displayName": "Employment Name",
                        "filterType": "default",
                        "filterId": "employmentName",
                        "fields": [],
                        "fieldTitles": [],
                        "numberMin": null,
                        "numberMax": null,
                        "numberInterval": null,
                        "dateFrom": null,
                        "dateTo": null,
                        "dateInterval": null,
                        "order": 1,
                        "sortType": null
                    }
                ]
            }
        ],
        "total_widgets": 21,
        "generated_at": "1776138403",
        "widget_breakdown": {
            "text": 9,
            "number": 7,
            "bar": 2,
            "hbar": 2,
            "pie": 0,
            "line": 0,
            "scatter": 0,
            "list": 1,
            "combo": 0,
            "embed": 0,
            "total": 21
        }
    },
    "generation_metadata": {
        "report_length": 5914,
        "widgets_extracted": 12,
        "widgets_explicit": 9,
        "data_sources_used": [],
        "processing_steps": [
            "Generated dashboard name",
            "Created empty dashboard",
            "Extracted widgets from report",
            "Generated widget payloads",
            "Positioned widgets on dashboard",
            "Submitted bulk create request"
        ]
    }
}