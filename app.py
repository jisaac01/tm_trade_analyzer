from flask import Flask, render_template, request, session, redirect, url_for, flash
import pandas as pd
from html import escape
import simulator
import replay
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
        # Get file_uuid from form (if reusing existing file) or URL
        file_uuid = request.form.get('file_uuid') or request.args.get('file_uuid')
        
        # Handle file upload (optional if file_uuid is provided)
        csv_file = request.files.get('csv_file')
        if csv_file and csv_file.filename:
            if not csv_file.filename.endswith('.csv'):
                flash('Please upload a valid CSV file.', 'error')
                return redirect(url_for('index'))
            # Save new file
            file_uuid = str(uuid.uuid4())
            filename = file_uuid + '.csv'
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            csv_file.save(filepath)
            session['csv_filepath'] = filepath
            session['csv_file_uuid'] = file_uuid
            session['original_filename'] = csv_file.filename
        elif file_uuid:
            # Reuse existing file
            filepath = os.path.join(UPLOAD_FOLDER, file_uuid + '.csv')
            if not os.path.exists(filepath):
                flash('The specified file no longer exists. Please upload a new CSV file.', 'error')
                return redirect(url_for('index'))
            session['csv_filepath'] = filepath
            session['csv_file_uuid'] = file_uuid
            # Keep original filename if it exists in session
        else:
            flash('Please upload a CSV file.', 'error')
            return redirect(url_for('index'))

        # Get parameters
        initial_balance = float(request.form.get('initial_balance', 10000))
        num_simulations = int(request.form.get('num_simulations', 1000))
        num_trades = int(request.form.get('num_trades', 60))
        option_commission = float(request.form.get('option_commission', 0.50))
        position_sizing_raw = request.form.get('position_sizing_mode', 'dynamic-percent')
        position_sizing, dynamic_risk_sizing = parse_position_sizing_mode(position_sizing_raw)
        simulation_mode = request.form.get('simulation_mode', 'iid')
        block_size = int(request.form.get('block_size', 5))
        risk_calculation_method = request.form.get('risk_calculation_method', 'conservative_theoretical')
        reward_calculation_method = request.form.get('reward_calculation_method', 'no_cap')

        # Store params in session for re-run
        session['params'] = {
            'initial_balance': initial_balance,
            'num_simulations': num_simulations,
            'num_trades': num_trades,
            'option_commission': option_commission,
            'position_sizing': position_sizing,
            'dynamic_risk_sizing': dynamic_risk_sizing,
            'simulation_mode': simulation_mode,
            'block_size': block_size,
            'risk_calculation_method': risk_calculation_method,
            'reward_calculation_method': reward_calculation_method,
            'position_sizing_display': position_sizing_raw,  # For display
            'allow_exceed_target_risk': 'allow_exceed_target_risk' in request.form  # Checkbox
        }

        return redirect(url_for('results'))

    # GET: render form
    # Populate form from URL parameters (for "open in new tab" feature)
    params = {}
    
    # Check URL parameters first, then fall back to session
    if request.args:
        params = {
            'initial_balance': float(request.args.get('initial_balance', 10000)),
            'num_simulations': int(request.args.get('num_simulations', 1000)),
            'num_trades': int(request.args.get('num_trades', 60)),
            'option_commission': float(request.args.get('option_commission', 0.50)),
            'position_sizing_display': request.args.get('position_sizing_mode', 'dynamic-percent'),
            'simulation_mode': request.args.get('simulation_mode', 'iid'),
            'block_size': int(request.args.get('block_size', 5)),
            'risk_calculation_method': request.args.get('risk_calculation_method', 'conservative_theoretical'),
            'reward_calculation_method': request.args.get('reward_calculation_method', 'no_cap'),
            'allow_exceed_target_risk': request.args.get('allow_exceed_target_risk') == 'true'
        }
        # Handle file_uuid from URL
        file_uuid = request.args.get('file_uuid')
        if file_uuid:
            filepath = os.path.join(UPLOAD_FOLDER, file_uuid + '.csv')
            if os.path.exists(filepath):
                # Store in session so form knows file is available
                params['file_uuid'] = file_uuid
                params['has_file'] = True
    else:
        params = session.get('params', {})
        if 'csv_file_uuid' in session:
            params['file_uuid'] = session['csv_file_uuid']
            params['has_file'] = True
    
    return render_template('index.html', 
                          original_filename=session.get('original_filename'),
                          **params)

@app.route('/results', methods=['GET', 'POST'])
def results():
    if 'csv_filepath' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Handle new CSV upload
        csv_file = request.files.get('csv_file')
        if csv_file and csv_file.filename:
            if not csv_file.filename.endswith('.csv'):
                flash('Please upload a valid CSV file.', 'error')
                return redirect(url_for('results'))
            file_uuid = str(uuid.uuid4())
            filename = file_uuid + '.csv'
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            csv_file.save(filepath)
            session['csv_filepath'] = filepath
            session['csv_file_uuid'] = file_uuid
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
            'risk_calculation_method': request.form.get('risk_calculation_method', params.get('risk_calculation_method', 'conservative_theoretical')),
            'reward_calculation_method': request.form.get('reward_calculation_method', params.get('reward_calculation_method', 'no_cap')),
            'allow_exceed_target_risk': 'allow_exceed_target_risk' in request.form  # Checkbox
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
        'block_size': 5,
        'position_sizing_display': 'dynamic-percent',
        'risk_calculation_method': 'conservative_theoretical',
        'reward_calculation_method': 'no_cap',
        'allow_exceed_target_risk': False  # Default: strict enforcement
    }
    params = session.get('params', default_params)
    params = {**default_params, **params}  # Ensure all defaults are present

    csv_filepath = session['csv_filepath']

    # Parse CSV
    try:
        trade_stats = trade_parser.parse_trade_csv(csv_filepath)
        trade_stats['name'] = os.path.splitext(session['original_filename'])[0]
    except Exception as e:
        flash(f'Error parsing CSV file: {str(e)}. Please check your trade data.', 'error')
        # Return to index page to allow user to upload a new file
        return redirect(url_for('index'))

    num_trades_per_simulation = max(params['num_trades'], trade_stats['num_trades'])

    # Initialize replay_data and replay_details_data in case of error
    replay_data = []
    replay_details_data = []
    
    try:
        # Run Monte Carlo simulation
        trade_reports = simulator.run_monte_carlo_simulation(
            trade_stats, params['initial_balance'], params['num_simulations'],
            position_sizing=params['position_sizing'],
            dynamic_risk_sizing=params['dynamic_risk_sizing'],
            simulation_mode=params['simulation_mode'],
            block_size=params['block_size'],
            commission_per_contract=params['option_commission'],
            num_trades=params['num_trades'],
            risk_calculation_method=params['risk_calculation_method'],
            reward_calculation_method=params['reward_calculation_method'],
            allow_exceed_target_risk=params['allow_exceed_target_risk']
        )
        
        # Run historical replay with same position sizing settings
        position_size_plan = simulator.build_position_size_plan(
            trade=trade_stats,
            initial_balance=params['initial_balance'],
            position_sizing=params['position_sizing'],
            risk_calculation_method=params['risk_calculation_method'],
            allow_exceed_target_risk=params['allow_exceed_target_risk']
        )
        
        replay_data = []
        replay_details_data = []  # Store per-scenario trade details
        for row in position_size_plan:
            ps = row['contracts']
            if params['position_sizing'] == 'percent':
                replay_result = replay.replay_actual_trades(
                    trade_stats=trade_stats,
                    initial_balance=params['initial_balance'],
                    position_sizing='percent',
                    target_risk_pct=row['target_risk_pct'],
                    dynamic_risk_sizing=params['dynamic_risk_sizing'],
                    risk_calculation_method=params['risk_calculation_method'],
                    allow_exceed_target_risk=params['allow_exceed_target_risk']
                )
            else:
                replay_result = replay.replay_actual_trades(
                    trade_stats=trade_stats,
                    initial_balance=params['initial_balance'],
                    position_sizing='contracts',
                    position_size=ps,
                    dynamic_risk_sizing=False,
                    risk_calculation_method=params['risk_calculation_method'],
                    allow_exceed_target_risk=params['allow_exceed_target_risk']
                )
            
            replay_data.append({
                'Contracts': ps,
                'Target Risk %': f"{row['target_risk_pct']:.2f}%",
                'Starting Risk %': f"{row['starting_risk_pct']:.2f}%",
                'Max Risk %': f"{row['max_risk_pct']:.2f}%" if len(replay_result['trade_details']) == 0 else f"{max(td['risk_pct'] for td in replay_result['trade_details']):.2f}%",
                'Final Balance': f"${replay_result['final_balance']:,.0f}",
                'Max Drawdown': f"${replay_result['max_drawdown']:,.0f}",
                'Max Losing Streak': f"{replay_result['max_losing_streak']:.0f}",
                'Num Trades': len(replay_result['trade_history']) - 1  # Exclude initial balance
            })
            
            # Store trade details for this scenario with scenario identifier
            replay_details_data.append({
                'scenario_id': f"scenario_{len(replay_data) - 1}",  # Use 0-based index
                'contracts': ps,
                'target_risk_pct': row['target_risk_pct'],
                'initial_balance': params['initial_balance'],
                'trade_details': replay_result['trade_details'],
                'final_balance': replay_result['final_balance']
            })
        
    except Exception as e:
        flash(f'Error running simulation: {str(e)}', 'error')
        # Render the results page with form but without results
        # This allows the user to adjust parameters and try again
        return render_template('results.html',
                              trade_reports=[],
                              replay_table_html='',
                              replay_details_data=replay_details_data,
                              raw_trade_data=trade_stats.get('raw_trade_data', []),
                              original_filename=session['original_filename'],
                              num_trades_per_simulation=0,
                              position_sizing_display_text='',
                              show_error_only=True,
                              **params)

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
        allow_exceed = params.get('allow_exceed_target_risk', False)
        
        # Rename Target Risk % to Risk Ceiling % when strict enforcement is enabled
        if position_sizing == 'percent' and not allow_exceed:
            table_df = table_df.rename(columns={'Target Risk %': 'Risk Ceiling %'})
        
        if position_sizing == 'contracts':
            # For contracts mode, rename Actual Risk % to Initial Risk % and drop Target Risk %
            table_df = table_df.rename(columns={'Actual Risk %': 'Initial Risk %'})
            table_df = table_df.drop(columns=['Target Risk %', 'Risk Ceiling %'], errors='ignore')
        report['table_html'] = table_df.to_html(index=False, classes='sim-table', border=0, escape=False)
        # Add tooltips to table headers, conditional on position_sizing
        if position_sizing == 'percent':
            contracts_title = "Initial number of contracts per trade for this risk percentage scenario. This starting count may be adjusted dynamically per trade based on current account balance and Dynamic Risk Sizing setting."
            if allow_exceed:
                target_risk_title = "The intended percentage of account balance to risk per trade. Used when Dynamic Risk Sizing is enabled to adjust contract count accordingly. Total risk may exceed this target."
                risk_col_name = 'Target Risk %'
            else:
                target_risk_title = "The maximum percentage of account balance that can be risked per trade (hard ceiling). No trades will be taken if they would exceed this limit. Used with Dynamic Risk Sizing to adjust contract count."
                risk_col_name = 'Risk Ceiling %'
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
                (f'<th>{risk_col_name}</th>', f'<th title="{target_risk_title}">{risk_col_name}</th>'),
                ('<th>Actual Risk %</th>', f'<th title="{actual_risk_title}">Actual Risk %</th>')
            ])
        else:
            replacements.append(('<th>Initial Risk %</th>', f'<th title="{initial_risk_title}">Initial Risk %</th>'))
        for old, new in replacements:
            report['table_html'] = report['table_html'].replace(old, new)

    # Prepare replay data table
    replay_df = pd.DataFrame(replay_data)
    
    # Rename Target Risk % to Risk Ceiling % when strict enforcement is enabled
    if params['position_sizing'] == 'percent' and not allow_exceed:
        replay_df = replay_df.rename(columns={'Target Risk %': 'Risk Ceiling %'})
    
    if params['position_sizing'] == 'contracts':
        # For contracts mode, rename and drop columns similar to Monte Carlo table
        replay_df = replay_df.rename(columns={'Starting Risk %': 'Initial Risk %'})
        replay_df = replay_df.drop(columns=['Target Risk %', 'Risk Ceiling %'], errors='ignore')
    replay_table_html = replay_df.to_html(index=False, classes='sim-table', border=0, escape=False)
    
    # Add tooltips to replay table headers
    replay_replacements = [
        ('<th>Contracts</th>', f'<th title="Number of contracts used for historical replay.">Contracts</th>'),
        ('<th>Final Balance</th>', '<th title="Actual final account balance after replaying all historical trades with this position sizing.">Final Balance</th>'),
        ('<th>Max Drawdown</th>', '<th title="Maximum peak-to-trough decline experienced during the historical replay.">Max Drawdown</th>'),
        ('<th>Max Losing Streak</th>', '<th title="Longest consecutive losing streak in the historical replay.">Max Losing Streak</th>'),
        ('<th>Num Trades</th>', '<th title="Number of trades completed before stopping (may be less than total if bankruptcy occurred).">Num Trades</th>')
    ]
    if params['position_sizing'] == 'percent':
        if allow_exceed:
            risk_title = "Target risk percentage used for historical replay. Total risk may exceed this target."
            risk_col = 'Target Risk %'
            starting_risk_title = "Risk percentage of the first trade (as % of initial balance). May exceed target due to rounding or if target risk enforcement is disabled."
        else:
            risk_title = "Maximum risk percentage allowed per trade (hard ceiling). No trades executed if they would exceed this limit."
            risk_col = 'Risk Ceiling %'
            starting_risk_title = "Risk percentage of the first trade (as % of initial balance). Never exceeds the risk ceiling when strict enforcement is enabled."
        replay_replacements.extend([
            (f'<th>{risk_col}</th>', f'<th title="{risk_title}">{risk_col}</th>'),
            ('<th>Starting Risk %</th>', f'<th title="{starting_risk_title}">Starting Risk %</th>')
        ])
    else:
        replay_replacements.append(('<th>Initial Risk %</th>', '<th title="Initial risk percentage for this contract count.">Initial Risk %</th>'))
    replay_replacements.append(('<th>Max Risk %</th>', '<th title="Maximum risk percentage actually taken during any trade in the historical replay (measured as risk/balance at time of trade). Shows 0% if no trades were executed.">Max Risk %</th>'))
    for old, new in replay_replacements:
        replay_table_html = replay_table_html.replace(old, new)

    # Calculate display text for header
    position_sizing_display_text = {
        'percent': 'Percentage of Account Balance',
        'contracts': 'Fixed Number of Contracts'
    }.get(params['position_sizing'], params['position_sizing'])

    return render_template('results.html',
                           trade_reports=trade_reports,
                           replay_table_html=replay_table_html,
                           replay_details_data=replay_details_data,
                           raw_trade_data=trade_stats.get('raw_trade_data', []),
                           original_filename=session['original_filename'],
                           csv_file_uuid=session.get('csv_file_uuid', ''),
                           num_trades_per_simulation=num_trades_per_simulation,
                           position_sizing_display_text=position_sizing_display_text,
                           **params)