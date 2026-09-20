"""AtlasQuant weekly profile research.

Measures when weekly highs/lows actually formed in a historical daily sample.
It tests day-of-week hypotheses statistically and never assumes that Tuesday or
Wednesday must form the weekly extreme.
"""
from __future__ import annotations

import pandas as pd

SCHEMA="ATLASQUANT_WEEKLY_PROFILE_V1"
WEEKDAY_NAMES={0:"Monday",1:"Tuesday",2:"Wednesday",3:"Thursday",4:"Friday",5:"Saturday",6:"Sunday"}


def analyze_weekly_extremes(daily: pd.DataFrame, *, min_days_per_week:int=4)->dict[str,object]:
    required={"datetime","high","low"}
    if not isinstance(daily,pd.DataFrame) or not required.issubset(daily.columns):
        return {
            "schema":SCHEMA,
            "weeks":0,
            "high_day_frequency_pct":{},
            "low_day_frequency_pct":{},
            "tuesday_wednesday_high_pct":None,
            "tuesday_wednesday_low_pct":None,
            "rows":[],
            "interpretation":"Dados insuficientes para estudo semanal.",
        }

    df=daily[["datetime","high","low"]].copy()
    df["datetime"]=pd.to_datetime(df["datetime"],utc=True,errors="coerce")
    df["high"]=pd.to_numeric(df["high"],errors="coerce")
    df["low"]=pd.to_numeric(df["low"],errors="coerce")
    df=df.dropna().sort_values("datetime")
    if df.empty:
        return analyze_weekly_extremes(pd.DataFrame(),min_days_per_week=min_days_per_week)

    local=df["datetime"].dt.tz_convert(None)
    df["week_start"]=(local-pd.to_timedelta(local.dt.weekday,unit="D")).dt.normalize()
    df["weekday"]=local.dt.weekday

    rows=[]
    for week,group in df.groupby("week_start",sort=True):
        if len(group)<max(1,int(min_days_per_week)):
            continue
        high_value=group["high"].max()
        low_value=group["low"].min()
        # First occurrence is deterministic if an equal extreme appears twice.
        high_row=group.loc[group["high"].eq(high_value)].iloc[0]
        low_row=group.loc[group["low"].eq(low_value)].iloc[0]
        rows.append({
            "week_start":pd.Timestamp(week).date().isoformat(),
            "days_observed":int(len(group)),
            "high_day":WEEKDAY_NAMES[int(high_row["weekday"])],
            "low_day":WEEKDAY_NAMES[int(low_row["weekday"])],
            "high":float(high_value),
            "low":float(low_value),
        })

    weeks=len(rows)
    if not weeks:
        return {
            "schema":SCHEMA,
            "weeks":0,
            "high_day_frequency_pct":{},
            "low_day_frequency_pct":{},
            "tuesday_wednesday_high_pct":None,
            "tuesday_wednesday_low_pct":None,
            "rows":[],
            "interpretation":"Nenhuma semana completa o suficiente para o critério informado.",
        }

    def frequencies(key:str)->dict[str,float]:
        counts={name:0 for name in WEEKDAY_NAMES.values()}
        for row in rows:
            counts[row[key]]+=1
        return {
            name:round(100.0*count/weeks,2)
            for name,count in counts.items()
            if count
        }

    high_freq=frequencies("high_day")
    low_freq=frequencies("low_day")
    tw={"Tuesday","Wednesday"}
    tw_high=round(100.0*sum(1 for x in rows if x["high_day"] in tw)/weeks,2)
    tw_low=round(100.0*sum(1 for x in rows if x["low_day"] in tw)/weeks,2)

    return {
        "schema":SCHEMA,
        "weeks":weeks,
        "high_day_frequency_pct":high_freq,
        "low_day_frequency_pct":low_freq,
        "tuesday_wednesday_high_pct":tw_high,
        "tuesday_wednesday_low_pct":tw_low,
        "rows":rows,
        "fixed_day_rule_assumed":False,
        "interpretation":(
            "Frequências históricas descrevem a amostra por ativo/período. "
            "Não provam comportamento institucional nem garantem repetição futura."
        ),
    }


__all__=["SCHEMA","WEEKDAY_NAMES","analyze_weekly_extremes"]
