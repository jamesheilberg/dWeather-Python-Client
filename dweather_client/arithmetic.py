"""
Some functions for organizing dWeather query results into formats relevant to Arbol's use cases.
Mainly related to summing and averaging over time.
"""
import numpy as np
import pandas as pd
from dweather_client.http_client import get_rainfall_dict
from dweather_client.utils import listify_period
import datetime

HISTORICAL_START_YEAR = 1981

def sum_period_rainfall(lat, lon, dataset, start_date, end_date, daily_cap=None, use_prelim=False, final_rev=None):
    ''' Download the rainfall data from ipfs and compute the rainfall for the given term
    Args:
        lat (float): latitude of grid cell
        lon (float): longitude of grid cell
        dataset (str): the rainfall dataset name in ipfs
        start_date (datetime.date): first date of term to include
        end_date (datetime.date): last date of term to include
        daily_cap (float): max rainfall in mm to count for a day
        use_prelim (bool): if true, include prelim data and get as much of the period as possible
    returns:
        (float, int, bool)
            float: the total rainfall
            int: the number of days in the period
            bool: true if all rainfall is in the 'Final' dataset
    Raises:
        DatasetError: If no matching dataset found on server
        InputOutOfRangeError: If the lat/lon is outside the dataset range in metadata
        CoordinateNotFoundError: If the lat/lon coordinate is not found on server
        DataMalformedError: If the grid cell file can't be parsed as rainfall data
    '''
    is_final = True
    if use_prelim:
        rainfall_dict, is_final = get_rev_rainfall_dict(lat, lon, dataset, end_date, final_rev)
        # The rainfall dict is sorted by date, so the last date will be the most recent (prelim) data
        # Need to check if the end date is in the rainfall dict, and if not, truncate the term to the end of the data
        if not is_final and end_date not in rainfall_dict:
            end_date = list(rainfall_dict)[-1]
    else:
        rainfall_dict = get_rainfall_dict(lat, lon, dataset)
    dates = listify_period(start_date, end_date)
    if daily_cap:
        rain = [min(rainfall_dict[date], daily_cap) for date in dates]
    else:
        rain = [rainfall_dict[date] for date in dates]
    return (sum(rain), len(rain), is_final)

def build_historical_rainfall_dict(lat, lon, dataset, start_date, end_date, daily_cap=None, start_year=HISTORICAL_START_YEAR, end_year=None, use_prelim=False, final_rev=None):
    ''' Builds a dict of rainfall values over the term period for each year for a grid cell
    Args:
        lat (float): latitude of grid cell
        lon (float): longitude of grid cell
        dataset (str): the rainfall dataset name in ipfs
        start_date (datetime.date): first date of term to include
        end_date (datetime.date): last date of term to include
        daily_cap (float): max rainfall in mm to count for a day
        start_year (int): the first year of historical data to include, using the start date
        end_year (int): the last year of data to include with the start_date year
        use_prelim (bool): if True, include prelim rainfall if there is not enough final rainfall
                if there is not enough rainfall including prelim then truncate the period to where we have data
    returns
        dict of int: (float, int): keys are the start date year for each term, values are
                a tuple of total rainfall and the number of days in the term for the term period starting that year
        bool is_final: true if all data included is from the final dataset
    Raises:
        DatasetError: If no matching dataset found on server
        InputOutOfRangeError: If the lat/lon is outside the dataset range in metadata
        CoordinateNotFoundError: If the lat/lon coordinate is not found on server
        DataMalformedError: If the grid cell file can't be parsed as rainfall data
    '''
    is_final = True
    if use_prelim:
        rainfall_dict, is_final = get_rev_rainfall_dict(lat, lon, dataset, end_date, final_rev)
        # The rainfall dict is sorted by date, so the last date will be the most recent (prelim) data
        # Need to check if the end date is in the rainfall dict, and if not, truncate the term to the end of the data
        if not is_final and end_date not in rainfall_dict:
            end_date = list(rainfall_dict)[-1]
    else:
        rainfall_dict = get_rainfall_dict(lat, lon, dataset)
    yearly_rainfall = {}
    if end_year is None:
        # If the end year is not provided they probably want all data up to the current year
        end_year = start_date.year
    for year in range(start_year, end_year + 1):
        historical_start = start_date.replace(year=year)
        # end date is tricky because it could be in the next calendar year
        historical_end = end_date.replace(year=year + (end_date.year - start_date.year))
        year_term = listify_period(historical_start, historical_end)
        if daily_cap:
            yearly_rain = [min(rainfall_dict[date], daily_cap) for date in year_term]
        else:
            yearly_rain = [rainfall_dict[date] for date in year_term]
        yearly_rainfall[year] = (sum(yearly_rain), len(yearly_rain))
    return yearly_rainfall, is_final


def sum_period_df(df, ps, pe, yrs, peril):
    """ 
    Get the sums of a peril by a defined period.
    
    return:
        pd.DataFrame indexed by year
        
    args:
        df = weather data with a daily index
        ps = contract start period, datetime.date object
        pe = contract end period, datetime.date object
        yrs = years lookback
        peril = the name of column you wish to sum
        
    """
    newdf = df
    years = np.array([])
    sums = np.array([])

    for year in range(ps.year-yrs, ps.year):
        if ps.year < pe.year: # if period crosses jan 1 into a new year
            left = str(year)+'-'+str(ps.month)+'-'+str(ps.day)
            right = str(year+1)+'-'+str(pe.month)+'-'+str(pe.day)
        else:
            left = str(year)+'-'+str(ps.month)+'-'+str(ps.day)
            right = str(year)+'-'+str(pe.month)+'-'+str(pe.day)

        sumChunk = newdf[left:right]
        years = np.append(years, int(year))
        sums = np.append(sums, sumChunk[peril].sum())
    return pd.DataFrame({'year': years, 'value': sums}).set_index("year")


def avg_period_df(df, ps, pe, yrs, peril):
    """ 
    Gets the avg of a peril by a defined period
    
    return:
        pd.DataFrame indexed by year
        
    args:
        df = weather data with a daily index
        ps = contract start period, datetime.date object
        pe = contract end period, datetime.date object
        yrs = years lookback
        peril = the name of column you wish to avg
        
    """

    newdf = df
    years = np.array([])
    avgs = np.array([])

    for year in range(ps.year-yrs, ps.year):
        if ps.year < pe.year: # if period crosses jan 1 into a new year
            left = str(year)+'-'+str(ps.month)+'-'+str(ps.day)
            right = str(year+1)+'-'+str(pe.month)+'-'+str(pe.day)
        else:
            left = str(year)+'-'+str(ps.month)+'-'+str(ps.day)
            right = str(year)+'-'+str(pe.month)+'-'+str(pe.day)

        sumChunk = newdf[left:right]
        years = np.append(years,int(year))
        avgs = np.append(avgs, sumChunk[peril].mean())
    return pd.DataFrame({'year': years, 'value': avgs}).set_index('year')
