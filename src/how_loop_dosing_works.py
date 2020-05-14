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
https://colab.research.google.com/gist/ed-nykaza/fe631aec6166a50b50ac9e8e5bc0eeb7/how-loop-dosing-decisions-work-etn-2020-05-11-v-0-1-0.ipynb

Credit for the color palette used in this animation goes to colorbrewer:
https://colorbrewer2.org/#type=qualitative&scheme=Set1&n=5
"""


# %% FUNCTIONS
def make_animation(scenario_df):
    inputs_from_file = input_table_to_dict(scenario_df)

    # first get the original prediction
    loop_output = update(inputs_from_file)
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

    original_forecast = loop_output.get("predicted_glucose_values")
    t = np.arange(0, len(original_forecast) * 5, 5)
    df = pd.DataFrame(t, columns=["time"])
    df["forecast"] = original_forecast
    df["forecast_type"] = "original"

    recommended_bolus = loop_output.get("recommended_bolus")[0]
    # TODO: subtract the effect of the temp basal. In the example, the temp basal = scheduled basal rate
    # so it is fine that this is not accounted for.
    carbs = int(carb_events["carb_values"][0])
    carb_to_insulin_ratio = np.round(carb_ratios["carb_ratio_values"][0], 2)
    insulin_to_cover_carbs = np.round(carbs / carb_to_insulin_ratio, 2)
    insulin_as_correction = np.round(recommended_bolus - insulin_to_cover_carbs, 2)

    original_bolus_amount = inputs_from_file.get("dose_values")[0]
    dosing_decision_df = pd.DataFrame()
    for dose_amount in np.arange(0, np.max([recommended_bolus + 0.1, insulin_to_cover_carbs + 0.05]), 0.05):
        temp_df = pd.DataFrame(t, columns=["time"])
        inputs_from_file["dose_values"] = [original_bolus_amount + dose_amount]
        temp_loop_output = update(inputs_from_file)
        temp_forecast = temp_loop_output.get("predicted_glucose_values")
        temp_df["forecast"] = temp_forecast
        temp_df["Forecast updated with Dose (U)"] = np.round(dose_amount, 2)
        dosing_decision_df = pd.concat([dosing_decision_df, temp_df], ignore_index=True, sort=False)

    # make an animation

    figure_title = "How Loop's Dosing Decision Works, Recommended Bolus of {}U =<br>{}U to cover {}g of carbs and {}U to prevent going below Dosing Safety Threshold".format(
        recommended_bolus, insulin_to_cover_carbs, carbs, insulin_as_correction
    )

    fig = px.line(
        dosing_decision_df,
        x="time",
        y="forecast",
        line_dash="Forecast updated with Dose (U)",
        line_dash_sequence=["dot"],
        line_shape="spline",
        animation_frame="Forecast updated with Dose (U)",
        range_y=[40, dosing_decision_df["forecast"].max() + 10],
        title=figure_title,
    )

    x_tick_vals = np.arange(-120, 400, 30)
    fig.update_layout(
        yaxis_title="Glucose (mg/dL)",
        xaxis_title="Time Relative to Current Time (t=0)",
        xaxis_tickvals=x_tick_vals,
        autosize=False,
        width=1200,
        height=700,
    )

    fig.add_trace(
        go.Scatter(
            name="CGM data leading up to the Forecast",
            x=np.arange(-(len(inputs_from_file["glucose_values"]) * 5) + 5, 5, 5),
            y=inputs_from_file["glucose_values"],
            mode="markers",
            marker_color="rgba(97,73,246, 0.75)",
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Original Forecast",
            x=t,
            y=original_forecast,
            mode="lines",
            line_color="rgba(97,73,246, 0.75)",
            line_width=4,
        )
    )

    forecast_with_rec_bolus = dosing_decision_df.loc[
        dosing_decision_df["Forecast updated with Dose (U)"] == np.round(recommended_bolus, 2), "forecast"
    ].values

    fig.add_trace(
        go.Scatter(
            name="Forecast with Bolus Rec. of {}U".format(recommended_bolus),
            x=t,
            y=forecast_with_rec_bolus,
            mode="lines",
            line_color="rgba(77,175,74, 0.75)",
            line_width=4,
        )
    )

    forecast_with_too_much_dose = dosing_decision_df.loc[
        dosing_decision_df["Forecast updated with Dose (U)"] == np.round(recommended_bolus + 0.05, 2), "forecast"
    ].values

    fig.add_trace(
        go.Scatter(
            name="Forecast with Dose of {}U".format(np.round(recommended_bolus + 0.05, 2)),
            x=t,
            y=forecast_with_too_much_dose,
            mode="lines",
            line_color="rgba(255,127,0, 0.75)",
            line_width=4,
        )
    )

    # add other traces

    # this only takes a single value TODO: update this to take a schedule
    suspend_threshold = df_settings.loc["suspend_threshold", "settings"]
    target_range_min = int(df_target_range["target_range_minimum_values"][0])
    target_range_max = int(df_target_range["target_range_maximum_values"][0])

    correction_range_mid = int(np.mean([target_range_min, target_range_max]))
    t_dosing_threshold = np.arange(0, 370, 1)
    dosing_threshold = np.append(
        np.ones(185) * suspend_threshold, np.linspace(suspend_threshold, correction_range_mid, 185),
    )

    # # calculate the amount of dose per time step
    # asdf = pd.DataFrame(original_forecast)
    # asdf.to_csv("original_forecast.csv")

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
            x=x_tick_vals,
            y=np.repeat(suspend_threshold, len(x_tick_vals)),
            mode="lines",
            line_color="rgb(228,26,28)",
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Dosing Safety Threshold",
            x=t_dosing_threshold,
            y=dosing_threshold,
            mode="lines",
            line_color="rgb(152,78,163)",
            line_width=4,
        )
    )

    return fig


if __name__ == "__main__":
    # %% LOAD DATA
    # filenames = [
    # "dosing-safety-threshold-example",
    # "dosing-safety-threshold-example-goes-below-suspend-threshold",
    # "dosing-safety-threshold-example-only-last-3-points",
    # "dosing-safety-threshold-example-only-last-2-points",
    # ]
    filenames = ["dosing-safety-threshold-example"]
    for filename in filenames:
        scenario = pd.read_csv(os.path.join("data", filename + ".csv"), index_col=[0])

        # %% MAKE THE FIGURE
        scenario_fig = make_animation(scenario)

        # %% PLOT AND SAVE FILE
        figure_location = os.path.join("figures", filename + ".html")
        plot(scenario_fig, filename=figure_location)
