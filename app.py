from flask import Flask, render_template, request, session, redirect, url_for, flash
import pandas as pd
from html import escape
import simulator
import trade_parser
import os
import uuid

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change this to a random secret in production


def parse_position_sizing_mode(position_sizing_raw):
    """Parse position sizing mode from form input to position_sizing and dynamic_risk_sizing."""
    if position_sizing_raw == 'fixed-percent':
        return 'percent', False
    elif position_sizing_raw == 'dynamic-percent':
        return 'percent', True
    else:  # contracts
        return 'contracts', False

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def format_currency_whole(value):
    value_int = int(value)
    formatted = f"{abs(value_int):,}"
    return f"-${formatted}" if value_int < 0 else f"${formatted}"

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Handle file upload
        csv_file = request.files.get('csv_file')
        if not csv_file or not csv_file.filename.endswith('.csv'):
            flash('Please upload a valid CSV file.')
            return redirect(url_for('index'))

        # Save file
        filename = str(uuid.uuid4()) + '.csv'
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        csv_file.save(filepath)
        session['csv_filepath'] = filepath
        session['original_filename'] = csv_file.filename

        # Get parameters
        initial_balance = float(request.form.get('initial_balance', 10000))
        num_simulations = int(request.form.get('num_simulations', 1000))
        option_commission = float(request.form.get('option_commission', 0.50))
        position_sizing_raw = request.form.get('position_sizing_mode', 'dynamic-percent')
        position_sizing, dynamic_risk_sizing = parse_position_sizing_mode(position_sizing_raw)
        simulation_mode = request.form.get('simulation_mode', 'iid')
        block_size = int(request.form.get('block_size', 1))

        # Store params in session for re-run
        session['params'] = {
            'initial_balance': initial_balance,
            'num_simulations': num_simulations,
            'option_commission': option_commission,
            'position_sizing': position_sizing,
            'dynamic_risk_sizing': dynamic_risk_sizing,
            'simulation_mode': simulation_mode,
            'block_size': block_size,
            'position_sizing_display': position_sizing_raw  # For display
        }

        return redirect(url_for('results'))

    # GET: render form
    return render_template('index.html')

@app.route('/results', methods=['GET', 'POST'])
def results():
    if 'csv_filepath' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Handle new CSV upload
        csv_file = request.files.get('csv_file')
        if csv_file and csv_file.filename:
            filename = str(uuid.uuid4()) + '.csv'
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            csv_file.save(filepath)
            session['csv_filepath'] = filepath
            session['original_filename'] = csv_file.filename

        # Update params from form
        params = session.get('params', {})
        position_sizing_raw = request.form.get('position_sizing_mode', params.get('position_sizing_display', 'dynamic-percent'))
        position_sizing, dynamic_risk_sizing = parse_position_sizing_mode(position_sizing_raw)
        params.update({
            'initial_balance': float(request.form.get('initial_balance', params.get('initial_balance', 10000))),
            'num_simulations': int(request.form.get('num_simulations', params.get('num_simulations', 1000))),
            'num_trades': int(request.form.get('num_trades', params.get('num_trades', 60))),
            'option_commission': float(request.form.get('option_commission', params.get('option_commission', 0.50))),
            'position_sizing': position_sizing,
            'dynamic_risk_sizing': dynamic_risk_sizing,
            'simulation_mode': request.form.get('simulation_mode', params.get('simulation_mode', 'iid')),
            'block_size': int(request.form.get('block_size', params.get('block_size', 1))),
            'position_sizing_display': position_sizing_raw,
            'risk_calculation_method': request.form.get('risk_calculation_method', params.get('risk_calculation_method', 'conservative_theoretical'))
        })
        session['params'] = params
        return redirect(url_for('results'))

    # GET: run simulation with current params
    default_params = {
        'initial_balance': 10000,
        'num_simulations': 1000,
        'num_trades': 60,
        'option_commission': 0.50,
        'position_sizing': 'percent',
        'dynamic_risk_sizing': True,
        'simulation_mode': 'iid',
        'block_size': 1,
        'position_sizing_display': 'dynamic-percent',
        'risk_calculation_method': 'conservative_theoretical'
    }
    params = session.get('params', default_params)
    params = {**default_params, **params}  # Ensure all defaults are present

    csv_filepath = session['csv_filepath']

    # Parse CSV
    trade_stats = trade_parser.parse_trade_csv(csv_filepath)
    trade_stats['name'] = os.path.splitext(session['original_filename'])[0]

    num_trades_per_simulation = max(params['num_trades'], trade_stats['num_trades'])

    try:
        # Run simulation
        trade_reports = simulator.run_monte_carlo_simulation(
            trade_stats, params['initial_balance'], params['num_simulations'],
            position_sizing=params['position_sizing'],
            dynamic_risk_sizing=params['dynamic_risk_sizing'],
            simulation_mode=params['simulation_mode'],
            block_size=params['block_size'],
            commission_per_contract=params['option_commission'],
            num_trades=params['num_trades'],
            risk_calculation_method=params['risk_calculation_method']
        )
    except Exception as e:
        flash(f'Error running simulation: {str(e)}. Please check your trade data.')
        return redirect(url_for('index'))

    # Prepare data for template
    for report in trade_reports:
        summary = report['summary']
        report['total_return_formatted'] = format_currency_whole(summary['total_return'])
        report['avg_win_formatted'] = format_currency_whole(summary['avg_win'])
        report['avg_loss_formatted'] = format_currency_whole(summary['avg_loss'])
        report['gross_gain_formatted'] = format_currency_whole(summary['gross_gain'])
        report['gross_loss_formatted'] = format_currency_whole(summary['gross_loss'])
        table_df = pd.DataFrame(report['table_rows'])
        position_sizing = params['position_sizing']
        if position_sizing == 'contracts':
            # For contracts mode, rename Actual Risk % to Initial Risk % and drop Target Risk %
            table_df = table_df.rename(columns={'Actual Risk %': 'Initial Risk %'})
            table_df = table_df.drop(columns=['Target Risk %'], errors='ignore')
        report['table_html'] = table_df.to_html(index=False, classes='sim-table', border=0, escape=False)
        # Add tooltips to table headers, conditional on position_sizing
        if position_sizing == 'percent':
            contracts_title = "Initial number of contracts per trade for this risk percentage scenario. This starting count may be adjusted dynamically per trade based on current account balance and Dynamic Risk Sizing setting."
            target_risk_title = "The intended percentage of account balance to risk per trade. Used when Dynamic Risk Sizing is enabled to adjust contract count accordingly."
            actual_risk_title = "The actual average risk percentage per trade across all simulations, accounting for dynamic adjustments and commissions. May differ from target due to rounding and fees."
        else:
            contracts_title = "Fixed number of contracts per trade. Higher values increase both potential gains and losses proportionally."
            initial_risk_title = "The fixed risk percentage per trade for this contract count. Calculated as (max risk per spread × contracts) / initial balance × 100."
        replacements = [
            ('<th>Contracts</th>', f'<th title="{contracts_title}">Contracts</th>'),
            ('<th>Avg Final $</th>', '<th title="Average final account balance across all simulations for this position size. Higher values indicate better expected performance, but consider risk metrics too.">Avg Final $</th>'),
            ('<th>Bankruptcy Prob</th>', '<th title="Probability of account balance reaching zero (bankruptcy) across simulations. Lower is better; indicates robustness of the strategy to adverse sequences.">Bankruptcy Prob</th>'),
            ('<th>Avg Max Drawdown</th>', '<th title="Average of the maximum drawdown (peak-to-trough decline) experienced in each simulation. Measures typical downside volatility.">Avg Max Drawdown</th>'),
            ('<th>Max Drawdown</th>', '<th title="The worst-case maximum drawdown observed across all simulations. Indicates the largest potential loss from peak to trough in any scenario.">Max Drawdown</th>'),
            ('<th>Avg Max Losing Streak</th>', '<th title="Average length of the longest consecutive losing streak in each simulation. Higher values indicate potential for prolonged periods of losses.">Avg Max Losing Streak</th>'),
            ('<th>Max Losing Streak</th>', '<th title="The longest consecutive losing streak observed in any simulation. Shows the worst-case sequence of losses possible under this sizing.">Max Losing Streak</th>')
        ]
        if position_sizing == 'percent':
            replacements.extend([
                ('<th>Target Risk %</th>', f'<th title="{target_risk_title}">Target Risk %</th>'),
                ('<th>Actual Risk %</th>', f'<th title="{actual_risk_title}">Actual Risk %</th>')
            ])
        else:
            replacements.append(('<th>Initial Risk %</th>', f'<th title="{initial_risk_title}">Initial Risk %</th>'))
        for old, new in replacements:
            report['table_html'] = report['table_html'].replace(old, new)

    # Calculate display text for header
    position_sizing_display_text = {
        'percent': 'Percentage of Account Balance',
        'contracts': 'Fixed Number of Contracts'
    }.get(params['position_sizing'], params['position_sizing'])

    return render_template('results.html',
                           trade_reports=trade_reports,
                           original_filename=session['original_filename'],
                           num_trades_per_simulation=num_trades_per_simulation,
                           position_sizing_display_text=position_sizing_display_text,
                           **params)