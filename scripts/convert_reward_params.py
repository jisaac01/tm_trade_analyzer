#!/usr/bin/env python3
"""
Helper to convert old reward_calculation_method values to new max_reward_method + take_profit_method.

Old system (deprecated):
- reward_calculation_method='no_cap'
- reward_calculation_method='cap_50pct_conservative_theoretical_max'
- reward_calculation_method='cap_25pct_theoretical_max'
- reward_calculation_method='cap_75pct_average_realized'
- reward_calculation_method='cap_40pct_conservative_realized_max'

New system:
- max_reward_method + take_profit_method

Conversion rules:
- 'no_cap' → max_reward_method='conservative_realized', take_profit_method='no_cap'
- 'cap_25pct_X' → max_reward_method=convert(X), take_profit_method='25pct'
- 'cap_40pct_X' → max_reward_method=convert(X), take_profit_method='40pct'
- 'cap_50pct_X' → max_reward_method=convert(X), take_profit_method='50pct'
- 'cap_75pct_X' → max_reward_method=convert(X), take_profit_method='75pct'

Where X converts to:
- 'conservative_theoretical_max' → 'conservative_theoretical'
- 'theoretical_max' → 'theoretical_max'
- 'average_realized' → 'max_realized' (closest match)
- 'conservative_realized_max' → 'conservative_realized'
"""

import re

def convert_reward_param(old_value):
    """Convert old reward_calculation_method to new params.
    
    Returns:
        tuple: (max_reward_method, take_profit_method)
    """
    if old_value == 'no_cap':
        return ('conservative_realized', 'no_cap')
    
    # Parse 'cap_XXpct_YYY' format
    match = re.match(r'cap_(\d+)pct_(.+)', old_value)
    if not match:
        raise ValueError(f"Unknown reward_calculation_method: {old_value}")
    
    pct = match.group(1)
    base = match.group(2)
    
    # Convert take profit percentage
    take_profit_method = f"{pct}pct"
    
    # Convert base reward method
    base_conversions = {
        'conservative_theoretical_max': 'conservative_theoretical',
        'theoretical_max': 'theoretical_max',
        'average_realized': 'max_realized',
        'conservative_realized_max': 'conservative_realized',
    }
    
    if base not in base_conversions:
        raise ValueError(f"Unknown base reward method: {base}")
    
    max_reward_method = base_conversions[base]
    
    return (max_reward_method, take_profit_method)


# Test the conversion
test_cases = [
    'no_cap',
    'cap_50pct_conservative_theoretical_max',
    'cap_25pct_theoretical_max',
    'cap_75pct_average_realized',
    'cap_40pct_conservative_realized_max',
]

print("Conversion Table:")
print("=" * 80)
for old in test_cases:
    new_max, new_cap = convert_reward_param(old)
    print(f"{old:45} → max_reward_method='{new_max}', take_profit_method='{new_cap}'")
