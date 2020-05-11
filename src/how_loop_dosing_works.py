# %% REQUIRED LIBRARIES
import os
import pandas as pd
import numpy as np
from plotly.offline import plot
import plotly.graph_objs as go
import plotly.express as px
from pyloopkit.loop_data_manager import update
from src.input_data_tools import input_table_to_dict, dict_inputs_to_dataframes

# %% REFERENCES
"""
A version of this code in google colab and stored in github gist is located here:
https://colab.research.google.com/gist/ed-nykaza/a456132822744f56f936168749fda83b/how-loop-dosing-works-etn-2020-05-09-v-0-1-0.ipynb

Credit for the color palette used in this animation goes to colorbrewer:
https://colorbrewer2.org/#type=qualitative&scheme=Set1&n=5
"""


# %% FUNCTIONS
def make_animation(scenario_df):
    inputs_from_file = input_table_to_dict(scenario_df)

    # first get the original prediction
    loop_output = update(inputs_from_file)

    original_forecast = loop_output.get("predicted_glucose_values")
    t = np.arange(0, len(original_forecast) * 5, 5)
    df = pd.DataFrame(t, columns=["time"])
    df["forecast"] = original_forecast
    df["forecast_type"] = "original"

    recommended_bolus = loop_output.get("recommended_bolus")[0]
    original_bolus_amount = inputs_from_file.get("dose_values")[0]
    dosing_decision_df = pd.DataFrame()
    for dose_amount in np.arange(0, recommended_bolus + 0.10, 0.05):
        temp_df = pd.DataFrame(t, columns=["time"])
        inputs_from_file["dose_values"] = [original_bolus_amount + dose_amount]
        temp_loop_output = update(inputs_from_file)
        temp_forecast = temp_loop_output.get("predicted_glucose_values")
        temp_df["forecast"] = temp_forecast
        temp_df["Forecast updated with Dose"] = np.round(dose_amount, 2)
        dosing_decision_df = pd.concat([dosing_decision_df, temp_df], ignore_index=True, sort=False)

    # make an animation
    fig = px.scatter(
        dosing_decision_df,
        x="time",
        y="forecast",
        animation_frame="Forecast updated with Dose",
        range_y=[40, dosing_decision_df["forecast"].max() + 10],
        title="How Loop's Dosing Decision Works<br>Recommended Bolus of {}U".format(recommended_bolus),
    )

    fig.update_layout(
        yaxis_title="Glucose (mg/dL)", xaxis_title="Time", autosize=False, width=1200, height=700,
    )

    fig.add_trace(
        go.Scatter(
            name="Original Forecast", x=t, y=original_forecast, mode="lines", line_color="rgb(97,73,246)", line_width=4,
        )
    )

    forecast_with_rec_bolus = dosing_decision_df.loc[
        dosing_decision_df["Forecast updated with Dose"] == np.round(recommended_bolus, 2), "forecast"
    ].values

    fig.add_trace(
        go.Scatter(
            name="Forecast with Bolus Rec. of {}U".format(recommended_bolus),
            x=t,
            y=forecast_with_rec_bolus,
            mode="lines",
            line_color="rgb(77,175,74)",
            line_width=4,
        )
    )

    forecast_with_too_much_dose = dosing_decision_df.loc[
        dosing_decision_df["Forecast updated with Dose"] == np.round(recommended_bolus + 0.05, 2), "forecast"
    ].values

    fig.add_trace(
        go.Scatter(
            name="Forecast with Dose of {}U".format(np.round(recommended_bolus + 0.05, 2)),
            x=t,
            y=forecast_with_too_much_dose,
            mode="lines",
            line_color="rgb(255,127,0)",
            line_width=4,
        )
    )

    # add other traces
    inputs = loop_output.get("input_data")
    # convert dict_inputs_to_dataframes
    (
        basal_rates,
        carb_events,
        carb_ratios,
        dose_events,
        blood_glucose,
        df_last_temporary_basal,
        df_misc,
        df_sensitivity_ratio,
        df_settings,
        df_target_range,
    ) = dict_inputs_to_dataframes(inputs)

    # this only takes a single value TODO: update this to take a schedule
    suspend_threshold = df_settings.loc["suspend_threshold", "settings"]
    target_range_min = int(df_target_range["target_range_minimum_values"][0])
    target_range_max = int(df_target_range["target_range_maximum_values"][0])

    correction_range_mid = int(np.mean([target_range_min, target_range_max]))
    t_dosing_threshold = np.arange(0, 370, 1)
    dosing_threshold = np.append(
        np.ones(185) * suspend_threshold, np.linspace(suspend_threshold, correction_range_mid, 185),
    )

    df["Suspend Threshold"] = suspend_threshold
    df["Correction Range Min"] = target_range_min
    df["Correction Range Max"] = target_range_max

    fig.add_trace(
        go.Scatter(
            name="Correction Min",
            x=df["time"],
            y=df["Correction Range Min"],
            fill=None,
            mode="lines",
            line_color="rgba(166,206,227, 0.50)",
            legendgroup="correction_range",
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Correction Range = {}-{} mg/dL".format(target_range_min, target_range_max),
            x=df["time"],
            y=df["Correction Range Max"],
            fill="tonexty",  # fill area between trace0 and trace1
            fillcolor="rgba(166,206,227, 0.25)",
            mode="lines",
            line_color="rgba(166,206,227, 0.50)",
            legendgroup="correction_range",
            opacity=0.05,
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Suspend Threshold = {} mg/dL".format(suspend_threshold),
            x=df["time"],
            y=df["Suspend Threshold"],
            mode="lines",
            line_color="rgb(228,26,28)",
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Dosing Threshold",
            x=t_dosing_threshold,
            y=dosing_threshold,
            mode="lines",
            line_color="rgb(152,78,163)",
            line_width=4,
        )
    )

    return fig


# %% LOAD DATA
filename = "dosing-threshold-example-1"
scenario = pd.read_csv(os.path.join("data", filename + ".csv"), index_col=[0])

# %% MAKE THE FIGURE
scenario_fig = make_animation(scenario)

# %% PLOT AND SAVE FILE
figure_location = os.path.join("figures", filename + ".html")
plot(scenario_fig, filename=figure_location)