import pandas as pd
import numpy as np
import json

# constructing the veneue object
class venue:
    # publisher related data that can be altered to fit the working data set
    publisher_fee = {
    2: 0.0030   # NASDAQ 
    }

    publisher_rebate = {
    2: 0.0020
    }

    def __init__(self, ask, ask_size, publisher_id):

        self.ask = ask
        self.ask_size = ask_size
        self.fee = venue.publisher_fee[publisher_id]
        self.rebate = venue.publisher_rebate[publisher_id]

# ------------------------------------------------------------------
# basic data loading and cleaning
def dataProcess(filepath):
    df = pd.read_csv(filepath, header = 0)
    col_index = df.columns[2:]
    df[col_index] = df[col_index].apply(pd.to_numeric, errors='coerce')
    df[['ts_event','ts_recv']] = df[['ts_event','ts_recv']].apply(pd.to_datetime)

    return df.sort_values('ts_event').groupby(['ts_event','publisher_id']).first().reset_index()

# ------------------------------------------------------------------
# Static allocator (exactly the same as provided in the pseudocode)
def compute_cost(split, venues, order_size, lambda_over, lambda_under ,theta_queue):
    executed = 0
    cash_spent = 0
    for i, v in enumerate(venues):
        exe = min(split[i], v.ask_size)
        executed   += exe
        cash_spent += exe * (v.ask + v.fee)
        maker_rebate = max(split[i]-exe, 0) * v.rebate
        cash_spent  -= maker_rebate

    underfill = max(order_size-executed, 0)
    overfill  = max(executed-order_size, 0)
    risk_pen  = theta_queue * (underfill + overfill)
    cost_pen  = lambda_under * underfill + lambda_over * overfill
    return cash_spent + risk_pen + cost_pen

def allocate(order_size, venues, lambda_over, lambda_under, theta_queue):
    step = 100                           # search in 100-share chunks
    splits = [[]]                        # start with an empty allocation list
    for v in venues:
        new_splits = []
        for alloc in splits:
            used = sum(alloc)
            max_v = min(order_size - used, v.ask_size)
            for q in range(0,max_v+1,step):
                new_splits.append(alloc + [q])
        splits = new_splits

    best_cost = float('inf')
    best_split = []
    for alloc in splits:
        if sum(alloc) != order_size: continue
        cost = compute_cost(alloc, venues, order_size, lambda_over, lambda_under, theta_queue)
        if cost < best_cost:
            best_cost  = cost
            best_split = alloc
    return best_split, best_cost

# ------------------------------------------------------------------
# back test code

def backtest(df, lambda_over, lambda_under, theta_queue, order_size = 5000):
    share_bought = 0
    total_spent = 0

    for t, group in df.groupby('ts_event', sort=True):
        if share_bought >= order_size:
            break

        venues = [venue(i['ask_px_00'], i['ask_sz_00'], i['publisher_id']) for _, i in group.iterrows()]

        # calculate the current allocation using allocate
        share_to_buy = order_size - share_bought
        alloc, _ = allocate(share_to_buy, venues, lambda_over, lambda_under, theta_queue)

        # calcuate the cost for this iteration step
        executed = 0
        cash_spent = 0.0

        # cost function as in compute_cost
        for i, share in enumerate(alloc):
            exe = min(share, venues[i].ask_size)
            executed   += exe
            cash_spent += exe * (venues[i].ask + venues[i].fee)
            maker_rebate = (share - exe) * venues[i].rebate
            cash_spent  -= maker_rebate

        total_spent += cash_spent
        share_bought += executed

    # penalties (if any)
    underfill = max(order_size - share_bought, 0)
    overfill = max(share_bought - order_size, 0)
    penalty = (lambda_under * underfill
               + lambda_over * overfill
               + theta_queue * (underfill + overfill))
    return total_spent + penalty

# ------------------------------------------------------------------
# random search for the optimal parameters
def parameter_optimization(df, iteration = 100):
    # Random search with a prescribed range

    lambda_over_best = 0
    lambda_under_best = 0
    theta_queue_best = 0
    least_cost = float('inf')

    rng = np.random.default_rng(114514)

    lambda_over_choices = rng.random(size=10) * 0.1
    lambda_under_choices = rng.random(size=10) * 0.5
    theta_queue_choices = rng.random(size=10) * 0.01


    for i in range(iteration):
        lambda_over = rng.choice(lambda_over_choices)
        lambda_under = rng.choice(lambda_under_choices)
        theta_queue = rng.choice(theta_queue_choices)

        cost = backtest(df, lambda_over, lambda_under, theta_queue)

        if cost < least_cost:
            least_cost = cost
            lambda_over_best = lambda_over
            lambda_under_best = lambda_under
            theta_queue_best = theta_queue

    # sanity check with emprical parameters
    for lambda_over, lambda_under, theta_queue in [
        [lambda_over_best, lambda_under_best, theta_queue_best],
        [0.01, 0.5, 0.005],   # empirical
        [0.02, 0.05, 0.001]    # risk-averse by choosing small parameters
    ]:
        cost = backtest(df, lambda_over, lambda_under, theta_queue)
        if cost < least_cost:
            least_cost = cost
            lambda_over_best = lambda_over
            lambda_under_best = lambda_under
            theta_queue_best = theta_queue

    return lambda_over_best, lambda_under_best, theta_queue_best, least_cost

# ------------------------------------------------------------------
# Baseline models

def best_ask_baseline(df, order_size = 5000):
    share_to_buy = order_size
    total_spent = 0

    for t, group in df.groupby('ts_event', sort = True):
        if share_to_buy <= 0:
            break

        best_venue = None
        least_price = float('inf')
        
        # find the best ask price
        for _, i in group.iterrows():
            if i['ask_px_00'] < least_price:
                least_price = i['ask_px_00']
                best_venue = venue(i['ask_px_00'], i['ask_sz_00'], i['publisher_id'])
            exe = min(share_to_buy, best_venue.ask_size)
            share_to_buy -= exe
            total_spent += exe * (best_venue.ask + best_venue.fee)

    return total_spent

def twap_baseline(df, order_size = 5000, bucket_window = 60): # window measured in seconds
    df = df.sort_values('ts_event')

    total_spent = 0.0
    share_to_buy = order_size

    # assign each entry in the data frame a bucket label
    start_time = df['ts_event'].min()
    df['bucket'] = ((df['ts_event'] - start_time).dt.total_seconds() // bucket_window).astype(int)

    # group data by bucket label
    groups = df.groupby('bucket')
    n_buckets = len(groups)
    share_per_bucket = (order_size // n_buckets) + 1
    
    for _, group in groups:
        if share_to_buy <= 0:
            break

        share_to_buy_bucket = share_per_bucket # track the number of shares that need to buy for this bucket
        for _, i in group.iterrows(): # iterate till required number of shares are purchased or all bucket entries have been processed
            if share_to_buy_bucket <= 0:
                break

            exe = min(share_to_buy_bucket, i.ask_sz_00, share_to_buy)
            price = i.ask_px_00 + venue.publisher_fee[i.publisher_id]
            total_spent += exe * price
            share_to_buy -= exe
            share_to_buy_bucket -= exe

    return total_spent


def vwap_baseline(df, order_size=5000):
    share_to_buy = order_size
    total_spent = 0.0

    for t, group in df.groupby('ts_event', sort=True):
        if share_to_buy <= 0:
            break

        # Compute total available size at this timestamp
        total_liquidity = group['ask_sz_00'].sum()
        if total_liquidity == 0:
            continue 

        for _, i in group.iterrows():
            v = venue(i['ask_px_00'], i['ask_sz_00'], i['publisher_id'])

            alloc = share_to_buy * (v.ask_size / total_liquidity)
            alloc = min(alloc, v.ask_size, share_to_buy) 
            alloc = int(alloc) 

            total_spent += alloc * (v.ask + v.fee)
            share_to_buy -= alloc

            if share_to_buy <= 0:
                break

    return total_spent

# Helper function
def base_point(val, baseline):
    return (baseline - val)/val * 10000
    
# ------------------------------------------------------------------
# Main
def main():
    df = dataProcess('l1_day.csv')

    # parameter optimization
    lambda_over, lambda_under, theta_queue, least_cost = parameter_optimization(df)

    # baseline models
    best_ask_cost = best_ask_baseline(df)
    twap_cost = twap_baseline(df)
    vwap_cost = vwap_baseline(df)

    output = {
        "optimal_parameters": {'lambda_over': float(lambda_over), 'lambda_under': float(lambda_under), 'theta_queue': float(theta_queue)},
        "result_from_optimal_parameters" : {'total_cost': float(least_cost), 'average_price': float(least_cost/5000)},
        "best_ask_baseline": {'total_cost': float(best_ask_cost), 'average_price': float(best_ask_cost/5000)},
        "twap_baseline": {'total_cost': float(twap_cost), 'average_price': float(twap_cost/5000)},
        "vwap_baseline": {'total_cost': float(vwap_cost), 'average_price': float(vwap_cost/5000)}
    }
    
    with open("backtest_results.json", "w") as f:
        json.dump(output, f, indent=4)

    return output

if __name__ == '__main__':
    print(main())