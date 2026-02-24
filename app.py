from flask import Flask, render_template, request
import pandas as pd
from html import escape
import simulator
import trade_parser
import os

app = Flask(__name__)

def format_currency_whole(value):
    value_int = int(value)
    return f"-${abs(value_int)}" if value_int < 0 else f"${value_int}"

@app.route('/', methods=['GET', 'POST'])
def index():
    # Hard-coded parameters
    csv_file = os.path.join(os.path.dirname(__file__), "tests", "test_data", "CML TM Trades Long 60 Delta, Short 30 Delta Call 20260223.csv")
    initial_balance = 10000
    num_simulations = 5000
    option_commission = 0.495
    position_sizing = 'percent'
    dynamic_risk_sizing = True
    simulation_mode = 'iid'
    block_size = 5

    # Parse CSV
    trade_stats = trade_parser.parse_trade_csv(csv_file)

    # Run simulation
    trade_reports = simulator.run_monte_carlo_simulation(
        trade_stats, initial_balance, num_simulations,
        position_sizing=position_sizing,
        dynamic_risk_sizing=dynamic_risk_sizing,
        simulation_mode=simulation_mode,
        block_size=block_size,
        commission_per_contract=option_commission
    )

    # Prepare data for template
    for report in trade_reports:
        summary = report['summary']
        report['total_return_formatted'] = format_currency_whole(summary['total_return'])
        report['avg_win_formatted'] = format_currency_whole(summary['avg_win'])
        report['avg_loss_formatted'] = format_currency_whole(summary['avg_loss'])
        report['gross_gain_formatted'] = format_currency_whole(summary['gross_gain'])
        report['gross_loss_formatted'] = format_currency_whole(summary['gross_loss'])
        table_df = pd.DataFrame(report['table_rows'])
        report['table_html'] = table_df.to_html(index=False, classes='sim-table', border=0, escape=False)

    return render_template('results.html',
                           trade_reports=trade_reports,
                           initial_balance=initial_balance,
                           position_sizing=position_sizing,
                           dynamic_risk_sizing=dynamic_risk_sizing,
                           simulation_mode=simulation_mode,
                           block_size=block_size)

if __name__ == '__main__':
    app.run(debug=True, port=5001)