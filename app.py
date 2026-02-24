from flask import Flask, render_template, request, session, redirect, url_for, flash
import pandas as pd
from html import escape
import simulator
import trade_parser
import os
import uuid

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change this to a random secret in production

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
        position_sizing = request.form.get('position_sizing_mode', 'percent')
        dynamic_risk_sizing = 'dynamic_risk_sizing' in request.form
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
            'block_size': block_size
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
        params.update({
            'initial_balance': float(request.form.get('initial_balance', params.get('initial_balance', 10000))),
            'num_simulations': int(request.form.get('num_simulations', params.get('num_simulations', 1000))),
            'option_commission': float(request.form.get('option_commission', params.get('option_commission', 0.50))),
            'position_sizing': request.form.get('position_sizing_mode', params.get('position_sizing', 'percent')),
            'dynamic_risk_sizing': 'dynamic_risk_sizing' in request.form,
            'simulation_mode': request.form.get('simulation_mode', params.get('simulation_mode', 'iid')),
            'block_size': int(request.form.get('block_size', params.get('block_size', 1)))
        })
        session['params'] = params
        return redirect(url_for('results'))

    # GET: run simulation with current params
    params = session.get('params', {
        'initial_balance': 10000,
        'num_simulations': 1000,
        'option_commission': 0.50,
        'position_sizing': 'percent',
        'dynamic_risk_sizing': True,
        'simulation_mode': 'iid',
        'block_size': 1
    })

    csv_filepath = session['csv_filepath']

    # Parse CSV
    trade_stats = trade_parser.parse_trade_csv(csv_filepath)
    trade_stats['name'] = os.path.splitext(session['original_filename'])[0]

    try:
        # Run simulation
        trade_reports = simulator.run_monte_carlo_simulation(
            trade_stats, params['initial_balance'], params['num_simulations'],
            position_sizing=params['position_sizing'],
            dynamic_risk_sizing=params['dynamic_risk_sizing'],
            simulation_mode=params['simulation_mode'],
            block_size=params['block_size'],
            commission_per_contract=params['option_commission']
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
        report['table_html'] = table_df.to_html(index=False, classes='sim-table', border=0, escape=False)

    return render_template('results.html',
                           trade_reports=trade_reports,
                           original_filename=session['original_filename'],
                           **params)