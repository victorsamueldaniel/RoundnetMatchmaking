# %%
import pandas as pd

df_adhesion = pd.read_excel("Adhésion au GRNA 2025-2026 (Responses).xlsx")[
    ["Prénom - First name", "Nom - Surname", "Genre - Gender"]
]
df_adhesion["NameSurname"] = (
    df_adhesion["Prénom - First name"] + df_adhesion["Nom - Surname"]
).str.replace(" ", "")
df_adhesion
# %%
df_level = pd.read_excel("levels.xlsx")[
    ["Prénom - First name", "Nom - Surname", "Niveau moyen"]
]
df_level["NameSurname"] = (
    df_level["Prénom - First name"] + df_level["Nom - Surname"]
).str.replace(" ", "")
# df_level.drop(columns=["Prénom - First name", "Nom - Surname"], inplace=True)
df_level
# %%
df_spectre = pd.read_excel(
    "Questionnaire SPECTRE (Responses).xlsx", sheet_name="Sheet1"
).drop(columns=["date"])
df_spectre = df_spectre[df_spectre["Name"] != 0]
df_spectre["NameSurname"] = (df_spectre["Name"] + df_spectre["Surname"]).str.replace(
    " ", ""
)
df_spectre.drop(columns=["Name", "Surname"], inplace=True)
df_spectre
# %%
df_inscription_level_spectre = pd.merge(
    df_level, df_spectre, on="NameSurname", how="outer"
)
df_inscription_level_spectre = pd.merge(
    df_adhesion, df_inscription_level_spectre, on="NameSurname", how="outer"
).drop(columns=["NameSurname"])
df_inscription_level_spectre["Prénom - First name"] = df_inscription_level_spectre[
    "Prénom - First name_x"
].combine_first(df_inscription_level_spectre["Prénom - First name_y"])
df_inscription_level_spectre["Nom - Surname"] = df_inscription_level_spectre[
    "Nom - Surname_x"
].combine_first(df_inscription_level_spectre["Nom - Surname_y"])
df_inscription_level_spectre.drop(columns=["Prénom - First name_x", "Prénom - First name_y", "Nom - Surname_x", "Nom - Surname_y"], inplace=True)

# df_inscription_level_spectre = df_inscription_level_spectre[
#     df_inscription_level_spectre["Prénom - First name"].notna()
# ]
df_inscription_level_spectre
# %%
df_inscription_level_spectre.to_excel("inscription_niveau_spectre.xlsx", index=False)
# %%
