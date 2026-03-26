import os
import numpy as np
import yaml
from yaml.loader import SafeLoader
import numpy_financial as npf
import plotly.graph_objects as go


class MultiFamily:

    def __init__(self) -> None:
        pass

    def get_config_data(self, config_filename=None):
        if config_filename is None:
            config_filename = 'multifamily_2.yaml'
        if not os.path.exists(config_filename):
            config_filename = os.path.join(os.path.dirname(__file__),
                                           config_filename)

        with open(config_filename) as f:
            config = yaml.load(f, Loader=SafeLoader)

        return config

    def add_missing_inputs(self, config):
        config = self.add_Purchase_Price(config)
        config = self.add_average_rent_per_unit(config)
        config = self.add_GPR(config)
        config = self.add_other_income(config)
        config = self.add_expenses(config)
        config = self.add_vacancy(config)
        config = self.add_property_management(config)
        config = self.add_NOI(config)
        config = self.add_acquisition_and_disposition_fees(config)
        config = self.add_asset_management(config)
        config = self.add_renovation_costs(config)

        return config

    def get_metrics(self, config):
        config = self.add_annual_loan_payment(config)
        config = self.add_interest_and_principle_pmts(config)
        config = self.add_cash_flows(config)
        config = self.add_cash_flow_metrics(config)
        config = self.add_partnership_waterfall_structure(config)
        config = self.add_irr(config)
        config = self.add_equity_multiple(config)
        config = self.add_loan_metrics(config)

        return config

    def add_other_income(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            if len(project['other_income']) == 0:
                other_income_dict = project['entry']['other_income_per_month']
                other_income_per_month = sum(other_income_dict.values())
                other_income_per_year = other_income_per_month * project[
                    'entry']['total_units'] * 12
                project['other_income'].append(round(other_income_per_year, 0))
                for years in range(0, project['hold_years']):
                    other_income_per_year = other_income_per_year * (
                        1 + project['rent_growth_rate'] / 100)
                    project['other_income'].append(
                        round(other_income_per_year, 0))

        return config

    def add_expenses(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            expense_dict = project['entry']['expenses_breakdown']
            expenses_per_unit_per_year = expense_dict['personnel']['per_unit_per_year'] + expense_dict[
                'general_and_administration']['per_unit_per_year'] + expense_dict[
                    'marketing']['per_unit_per_year'] + expense_dict['turnover'][
                        'per_unit_per_year'] + expense_dict['repair_and_maintenance'][
                            'per_unit_per_year'] + expense_dict['contract_servies'][
                                'per_unit_per_year'] + expense_dict['utilities'][
                                    'per_unit_per_year'] + expense_dict['utilities'][
                                        'reimbursments_per_unit_per_year'] + expense_dict[
                                            'property_taxes'][
                                                'per_unit_per_year'] + expense_dict[
                                                    'insurance'][
                                                        'per_unit_per_year'] + expense_dict[
                                                            'capital_expense_reserve'][
                                                                'per_unit_per_year']

            expenses_per_year = -1 * expenses_per_unit_per_year * project[
                'entry']['total_units']

            project['expenses'].append(round(expenses_per_year, 0))
            for years in range(0, project['hold_years']):
                expenses_per_year = expenses_per_year * (
                    1 + project['expense_growth_rate'] / 100)
                project['expenses'].append(round(expenses_per_year, 0))

        return config

    def add_vacancy(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            GPR = project['GPR']
            other_income = project['other_income']
            vacancy_percent = project['vacancy']['percent']
            project['vacancy']['amount'] = [
                -(gpr_item + other_income_item) * vacancy_percent / 100
                for gpr_item, other_income_item in zip(GPR, other_income)
            ]

        return config

    def add_property_management(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            GPR = project['GPR']
            other_income = project['other_income']
            vacancy = project['vacancy']['amount']
            expenses = project['expenses']
            percent_of_EGR = project['property_management_fee'][
                'percent_of_EGR']
            for years in range(0, project['hold_years'] + 1):
                property_management = -1 * (
                    GPR[years] + other_income[years] +
                    vacancy[years]) * percent_of_EGR / 100
                project['property_management_fee']['amount'].append(
                    round(property_management, 0))

        return config

    def add_acquisition_and_disposition_fees(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            Purchase_Price = project['entry']['Purchase_Price']
            NOI = project['NOI']['amount']
            sale_proceeds = NOI[-1] / project['exit']['Cap_Rate'] * 100

            if project['entry']['acquisition_fee']['amount'] is None:
                entry_acquisition_costs = Purchase_Price * project['entry'][
                    'acquisition_fee']['percentage'] / 100
                project['entry']['acquisition_fee'][
                    'amount'] = entry_acquisition_costs
            if project['exit']['disposition_fee']['amount'] is None:
                exit_disposition_fee = sale_proceeds * project['exit'][
                    'disposition_fee']['percentage'] / 100
                project['exit']['disposition_fee'][
                    'amount'] = exit_disposition_fee

        return config

    def add_asset_management(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            cash_flow = project['cash_flow']
            Purchase_Price = project['entry']['Purchase_Price']
            entry_closing_costs = project['entry']['closing_cost']['amount']
            entry_acquisition_costs = project['entry']['acquisition_fee'][
                'amount']

            if len(cash_flow['leveraged_cash_flow']) == 0:
                unleveraged_cash_flow_item = -Purchase_Price - entry_closing_costs - entry_acquisition_costs

            else:
                unleveraged_cash_flow_item = cash_flow['leveraged_cash_flow'][0]

            loan_amount = project['finance']['loan']['Amount']
            loan_origination_fee = loan_amount * project['finance']['loan'][
                'loan_fee_percent'] / 100
            leveraged_cash_flow_item = unleveraged_cash_flow_item + loan_amount - loan_origination_fee
            asset_management_fee_percent = project['asset_management_fee'][
                'percent']
            asset_management_fee_amount = -leveraged_cash_flow_item * asset_management_fee_percent / 100
            project['asset_management_fee']['amount'] = [
                asset_management_fee_amount
            ] * project['hold_years']

        return config

    def add_NOI(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]

            if len(project['NOI']['amount']) == 0:
                if project['entry']['Cap_Rate'] is None:
                    GPR = project['GPR']
                    other_income = project['other_income']
                    vacancy_amount = project['vacancy']['amount']
                    expenses = project['expenses']
                    property_management = project['property_management_fee'][
                        'amount']
                    for years in range(0, project['hold_years'] + 1):
                        noi_year = GPR[years] + other_income[
                            years] + vacancy_amount[years] + expenses[
                                years] + property_management[years]
                        project['NOI']['amount'].append(round(noi_year, 0))

                else:
                    noi_year = project['entry']['Purchase_Price'] * project[
                        'entry']['Cap_Rate'] / 100

                    project['NOI']['amount'].append(round(noi_year, 2))
                    for years in range(0, project['hold_years']):
                        noi_year = noi_year * (
                            1 + project['NOI']['growth_rate'] / 100)
                        project['NOI']['amount'].append(round(noi_year, 2))

        return config

    def add_renovation_costs(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]

            renovation_costs_amount = project['entry']['renovation_costs'][
                'amount']

            cost_percentage_array = project['entry']['renovation_costs'][
                'yearly_percent']
            cost_percentage_array = cost_percentage_array + [0] * (
                project['hold_years'] + 1 - len(cost_percentage_array))

            fee_percentage_array = project['entry']['renovation_costs'][
                'construction_management_fee']['yearly_percent']
            fee_percentage_array = fee_percentage_array + [0] * (
                project['hold_years'] + 1 - len(fee_percentage_array))

            if len(project['renovation_costs']) == 0:
                project['renovation_costs'] = [
                    renovation_costs_amount * cost_percentage_array[years] *
                    (1 + fee_percentage_array[years] / 100) / 100
                    for years in range(0, 10)
                ]

        return config

    def add_partnership_waterfall_structure(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            equity = project['finance']['equity']
            leveraged_cash_flow = project['cash_flow']['leveraged_cash_flow']

            gp_equity_percent = equity['general_partner']['equity_percent']
            if len(equity['general_partner']['equity_contributions']
                  ) == 0 and gp_equity_percent is not None:
                gp_equity_amount = leveraged_cash_flow[0] * equity[
                    'general_partner']['equity_percent'] / 100
                equity['general_partner']['equity_contributions'].append(
                    gp_equity_amount)
                equity['general_partner'][
                    'equity_contributions'] = equity['general_partner'][
                        'equity_contributions'] + [0] * project['hold_years']

            lp_equity_percent = equity['limited_partner']['equity_percent']
            if len(equity['limited_partner']
                   ['equity_contributions']) == 0 and lp_equity_percent is None:
                lp_equity_percent = 100 - gp_equity_percent
                equity['limited_partner']['equity_percent'] = lp_equity_percent
                lp_equity_amount = leveraged_cash_flow[0] - gp_equity_amount
                equity['limited_partner']['equity_contributions'].append(
                    lp_equity_amount)
                equity['limited_partner'][
                    'equity_contributions'] = equity['limited_partner'][
                        'equity_contributions'] + [0] * project['hold_years']

            preferred_return_percent = equity['preferred_return_percent']
            lp_preferred_interest = []
            lp_distributions = []
            lp_beginning_balance = [
                -equity['limited_partner']['equity_contributions'][0]
            ]

            for years in range(0, 10):
                lp_preferred_interest_item = lp_beginning_balance[
                    years] * preferred_return_percent / 100
                lp_preferred_interest.append(
                    round(lp_preferred_interest_item, 2))
                lp_leveraged_cash_flow_portion = leveraged_cash_flow[
                    years + 1] * lp_equity_percent / 100

                lp_distribution_item = 0
                if lp_leveraged_cash_flow_portion > 0:
                    if (lp_beginning_balance[years] + lp_preferred_interest_item
                       ) < lp_leveraged_cash_flow_portion:
                        lp_distribution_item = lp_beginning_balance[
                            years] + lp_preferred_interest_item
                    else:
                        lp_distribution_item = lp_leveraged_cash_flow_portion
                lp_distributions.append(round(lp_distribution_item, 2))

                lp_beginning_balance_item = lp_beginning_balance[
                    years] + lp_preferred_interest_item - lp_distribution_item
                lp_beginning_balance.append(round(lp_beginning_balance_item, 2))

            equity['limited_partner'][
                'preferred_interest'] = lp_preferred_interest
            equity['limited_partner']['distributions'] = lp_distributions
            equity['limited_partner'][
                'beginning_balance'] = lp_beginning_balance

            gp_preferred_interest = []
            gp_distributions = []
            gp_beginning_balance = [
                -equity['general_partner']['equity_contributions'][0]
            ]

            for years in range(0, 10):
                gp_preferred_interest_item = gp_beginning_balance[
                    years] * preferred_return_percent / 100
                gp_preferred_interest.append(
                    round(gp_preferred_interest_item, 2))
                gp_leveraged_cash_flow_portion = leveraged_cash_flow[
                    years + 1] * gp_equity_percent / 100

                gp_distribution_item = 0
                if gp_leveraged_cash_flow_portion > 0:
                    if (gp_beginning_balance[years] + gp_preferred_interest_item
                       ) < gp_leveraged_cash_flow_portion:
                        gp_distribution_item = gp_beginning_balance[
                            years] + gp_preferred_interest_item
                    else:
                        gp_distribution_item = gp_leveraged_cash_flow_portion
                gp_distributions.append(round(gp_distribution_item, 2))

                gp_beginning_balance_item = gp_beginning_balance[
                    years] + gp_preferred_interest_item - gp_distribution_item
                gp_beginning_balance.append(round(gp_beginning_balance_item, 2))

            equity['general_partner'][
                'preferred_interest'] = gp_preferred_interest
            equity['general_partner']['distributions'] = gp_distributions
            equity['general_partner'][
                'beginning_balance'] = gp_beginning_balance

            equity['sale_cash_for_final_split'] = leveraged_cash_flow[
                -1] - lp_distributions[-1] - gp_distributions[-1]

            promotion_over_preferred_return_percent = equity[
                'promotion_over_preferred_return_percent']
            lp_cash_flow = []
            lp_cash_flow.append(
                equity['limited_partner']['equity_contributions'][0])
            lp_cash_flow = lp_cash_flow + lp_distributions
            lp_cash_flow[-1] = round(
                lp_cash_flow[-1] +
                equity['sale_cash_for_final_split'] * lp_equity_percent / 100 *
                (1 - promotion_over_preferred_return_percent / 100), 2)
            equity['limited_partner']['cash_flow'] = lp_cash_flow

            gp_cash_flow = []
            gp_cash_flow.append(
                equity['general_partner']['equity_contributions'][0])
            gp_cash_flow = gp_cash_flow + gp_distributions
            gp_cash_flow[-1] = round(
                gp_cash_flow[-1] +
                equity['sale_cash_for_final_split'] * gp_equity_percent / 100 +
                equity['sale_cash_for_final_split'] * lp_equity_percent / 100 *
                promotion_over_preferred_return_percent / 100, 2)
            equity['general_partner']['cash_flow'] = gp_cash_flow

        return config

    def add_average_rent_per_unit(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            if project['entry']['average_rent_per_unit'] is None:
                unit_mix = project['unit_mix']
                total_units = sum([unit['number'] for unit in unit_mix])
                average_rent_per_unit = sum([
                    unit['number'] * unit['rent'] for unit in unit_mix
                ]) / total_units

                project['entry']['total_units'] = total_units
                project['entry'][
                    'average_rent_per_unit'] = average_rent_per_unit

        return config

    def add_GPR(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            if len(project['GPR']) == 0:
                GPR = project['entry']['total_units'] * project['entry'][
                    'average_rent_per_unit'] * 12
                project['GPR'].append(round(GPR, 0))
                for years in range(0, project['hold_years']):
                    GPR = GPR * (1 + project['rent_growth_rate'] / 100)
                    project['GPR'].append(round(GPR, 0))

        return config

    def add_Purchase_Price(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            if project['entry']['Purchase_Price'] is None:
                project['Purchase_Price'] = project['NOI']['Amount'][
                    0] / project['entry']['Cap_Rate'] * 100

        return config

    def add_Cap_Rate(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]

            cap_rate_based_on_NOI = None
            if len(project['entry']['NOI']['Amount']) > 0:
                cap_rate_based_on_NOI = project['NOI']['Amount'][0] / project[
                    'Purchase_Price'] * 100
            cap_rate_based_on_GPR = None
            if len(project['entry']['GPR']) > 0:
                cap_rate_based_on_GPR = project['entry']['GPR'][0]
            if cap_rate_based_on_NOI is not None and cap_rate_based_on_GPR is not None:
                cap_rate_diff = abs(cap_rate_based_on_NOI -
                                    cap_rate_based_on_GPR)
                assert cap_rate_diff < 0.3
                print(
                    f"Cap Rate difference using NOI & GPR differ by {cap_rate_diff}"
                )
            if project['entry']['Cap_Rate'] is None:
                project['entry']['Cap_Rate'] = cap_rate_based_on_NOI

        return config

    def add_annual_loan_payment(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            if 'finance' in project and (
                    project['finance']['loan']['annual_loan_payment'] is None):
                monthly_rate = project['finance']['loan']['r'] / 12 / 100
                terms = project['finance']['loan']['Amortization'] * 12
                loan_amount = project['finance']['loan']['Amount']
                monthly_pmt = (npf.pmt(monthly_rate, terms, loan_amount)) * -1
                project['finance']['loan']['annual_loan_payment'] = round(
                    monthly_pmt * 12, 2)

        return config

    def add_interest_and_principle_pmts(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            if 'finance' in project and 'cash_flow' in project:
                monthly_rate = project['finance']['loan']['r'] / 12 / 100
                terms = project['finance']['loan']['Amortization'] * 12
                loan_amount = project['finance']['loan']['Amount']
                n_per = np.arange(project['hold_years'] * 12) + 1
                monthly_ipmt = npf.ipmt(monthly_rate, n_per, terms, loan_amount)
                monthly_ppmt = npf.ppmt(monthly_rate, n_per, terms, loan_amount)

                for years in range(0, project['hold_years']):
                    start_index = 12 * (years)
                    end_index = start_index + 12
                    project['cash_flow']['interest_payment'].append(
                        round(monthly_ipmt[start_index:end_index].sum(), 2))
                    project['cash_flow']['principle_payment'].append(
                        round(monthly_ppmt[start_index:end_index].sum(), 2))

        return config

    def add_cash_flow_metrics(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]

            NOI = project['NOI']['amount']
            renovation_costs = project['renovation_costs']
            principle_payment = project['cash_flow']['principle_payment']
            interest_payment = project['cash_flow']['interest_payment']
            asset_management_fee_amount = project['asset_management_fee'][
                'amount']

            equity_capital_and_fees = -project['cash_flow'][
                'leveraged_cash_flow'][0]

            if len(project['cash_flow']['free_cash_flow']) == 0:
                free_cash_flow = [
                    NOI[i] - renovation_costs[i] + principle_payment[i] +
                    interest_payment[i] - asset_management_fee_amount[i]
                    for i in range(0, 10)
                ]
                project['cash_flow']['free_cash_flow'] = free_cash_flow

            if len(project['cash_flow']['cash_on_cash_return']) == 0:
                cash_on_cash_return = [
                    round(item / equity_capital_and_fees * 100, 2)
                    for item in free_cash_flow
                ]

                project['cash_flow'][
                    'cash_on_cash_return'] = cash_on_cash_return

        return config

    def add_cash_flows(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            cash_flow = project['cash_flow']

            Purchase_Price = project['entry']['Purchase_Price']
            entry_closing_costs = project['entry']['closing_cost']['amount']
            entry_acquisition_costs = project['entry']['acquisition_fee'][
                'amount']
            loan_amount = project['finance']['loan']['Amount']

            NOI = project['NOI']['amount']
            renovation_costs = project['renovation_costs']
            asset_management_fee_amount = project['asset_management_fee'][
                'amount']

            sale_proceeds = NOI[-1] / project['exit']['Cap_Rate'] * 100
            sale_closing_cost = sale_proceeds * project['exit'][
                'closing_cost_percentage'] / 100

            exit_disposition_fee = project['exit']['disposition_fee']['amount']

            principle_payment = project['cash_flow']['principle_payment']
            interest_payment = project['cash_flow']['interest_payment']
            loan_payoff = sum(project['cash_flow']['principle_payment']
                             ) + project['finance']['loan']['Amount']

            if len(cash_flow['unleveraged_cash_flow']) == 0:
                unleveraged_cash_flow = []
                unleveraged_cash_flow_item = -Purchase_Price - entry_closing_costs - entry_acquisition_costs
                unleveraged_cash_flow.append(unleveraged_cash_flow_item)
                for years in range(0, project['hold_years']):
                    unleveraged_cash_flow_item = NOI[years] - renovation_costs[
                        years] - asset_management_fee_amount[years]
                    unleveraged_cash_flow.append(
                        round(unleveraged_cash_flow_item, 1))

                unleveraged_cash_flow[-1] = unleveraged_cash_flow[
                    -1] + sale_proceeds - sale_closing_cost - exit_disposition_fee
                cash_flow['unleveraged_cash_flow'] = unleveraged_cash_flow

            if len(cash_flow['leveraged_cash_flow']) == 0:
                leveraged_cash_flow = []
                loan_origination_fee = loan_amount * project['finance']['loan'][
                    'loan_fee_percent'] / 100
                leveraged_cash_flow_item = unleveraged_cash_flow[
                    0] + loan_amount - loan_origination_fee
                leveraged_cash_flow.append(round(leveraged_cash_flow_item, 1))

                leveraged_cash_flow_0_to_10 = [
                    unleveraged_cash_flow[i + 1] + principle_payment[i] +
                    interest_payment[i] for i in range(0, 10)
                ]
                leveraged_cash_flow = leveraged_cash_flow + leveraged_cash_flow_0_to_10
                leveraged_cash_flow[-1] = leveraged_cash_flow[-1] - loan_payoff
                cash_flow['leveraged_cash_flow'] = leveraged_cash_flow

        return config

    def add_irr(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            equity = project['finance']['equity']

            leveraged_cash_flow = project['cash_flow']['leveraged_cash_flow']
            irr = npf.irr(leveraged_cash_flow) * 100
            project['cash_flow']['irr'] = round(irr, 4)

            gp_cash_flow = equity['general_partner']['cash_flow']
            gp_irr = npf.irr(gp_cash_flow) * 100
            equity['general_partner']['irr'] = round(gp_irr, 2)

            lp_cash_flow = equity['limited_partner']['cash_flow']
            lp_irr = npf.irr(lp_cash_flow) * 100
            equity['limited_partner']['irr'] = round(lp_irr, 2)

        return config

    def add_equity_multiple(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]
            equity = project['finance']['equity']

            equity_capital_and_fees = -project['cash_flow'][
                'leveraged_cash_flow'][0]

            leveraged_cash_flow = project['cash_flow']['leveraged_cash_flow']
            equity_multiple = sum(
                leveraged_cash_flow[1:]) / equity_capital_and_fees
            project['cash_flow']['equity_multiple'] = round(equity_multiple, 4)

            gp_cash_flow = equity['general_partner']['cash_flow']
            gp_positive_cash_flow = sum(
                [item if item > 0 else 0 for item in gp_cash_flow])
            gp_equity = -1 * sum(
                [item if item < 0 else 0 for item in gp_cash_flow])
            gp_equity_multiple = gp_positive_cash_flow / gp_equity
            equity['general_partner']['equity_multiple'] = round(
                gp_equity_multiple, 2)

            lp_cash_flow = equity['limited_partner']['cash_flow']
            lp_positive_cash_flow = sum(
                [item if item > 0 else 0 for item in lp_cash_flow])
            lp_equity = -1 * sum(
                [item if item < 0 else 0 for item in lp_cash_flow])
            lp_equity_multiple = lp_positive_cash_flow / lp_equity
            equity['limited_partner']['equity_multiple'] = round(
                lp_equity_multiple, 2)

        return config

    def add_loan_metrics(self, config):
        for proj_num in range(0, len(config['projects'])):
            project = config['projects'][proj_num]

            loan_amount = project['finance']['loan']['Amount']
            Purchase_Price = project['entry']['Purchase_Price']
            ltv = loan_amount / Purchase_Price * 100
            project['finance']['loan']['ltv'] = round(ltv, 2)

            renovation_costs = sum(project['renovation_costs'])
            exit_closing_cost = loan_amount * project['exit'][
                'closing_cost_percentage'] / 100
            ltc = loan_amount / (Purchase_Price + renovation_costs +
                                 exit_closing_cost) * 100
            project['finance']['loan']['ltc'] = round(ltc, 2)

            NOI_amount = project['NOI']['amount']
            dscr = NOI_amount[0] / project['finance']['loan'][
                'annual_loan_payment']
            project['finance']['loan']['dscr'] = round(dscr, 2)

            debt_ratio = NOI_amount[0] / loan_amount * 100
            project['finance']['loan']['debt_ratio'] = round(debt_ratio, 2)

        return config


class MultiFamilyCharts:

    def __init__(self) -> None:
        self.hold_years = []
        self.Name = []
        self.irr = []
        self.equity_multiple = []
        self.cash_flow_return = []
        self.free_cash_flow = []
        self.principle_payment = []
        self.interest_payment = []
        self.unleveraged_cash_flow = []
        self.leveraged_cash_flow = []

    def get_common_chart_data(self, outputs=None):
        for output in outputs:
            proj = output['projects'][0]
            self.hold_years.append(proj['hold_years'])
            self.Name.append(proj['Name'])
            self.irr.append(proj['cash_flow']['irr'])
            self.equity_multiple.append(proj['cash_flow']['equity_multiple'])
            self.cash_flow_return.append(
                proj['cash_flow']['cash_on_cash_return'])
            self.free_cash_flow.append([0] +
                                       proj['cash_flow']['free_cash_flow'])
            self.principle_payment.append(
                [0] + proj['cash_flow']['principle_payment'])
            self.interest_payment.append([0] +
                                         proj['cash_flow']['interest_payment'])
            self.unleveraged_cash_flow.append(
                proj['cash_flow']['unleveraged_cash_flow'])
            self.leveraged_cash_flow.append(
                proj['cash_flow']['leveraged_cash_flow'])

        self.plot_years = list(range(1, max(self.hold_years) + 1))

    def get_all_charts(self, output_folder):
        self.get_irr_chart(output_folder)
        self.get_equity_multiple_chart(output_folder)
        self.get_cash_flow_chart(output_folder)
        self.get_cash_flow_return_chart(output_folder)

    def get_irr_chart(self, output_folder):

        data = []
        layout = {
            'xaxis': {
                'title': 'Project'
            },
            'yaxis': {
                'range': [0, 20],
                'title': 'IRR (%)'
            },
            'title': 'Comparison of Project IRR'
        }
        data.append(go.Bar(name="IRR", x=self.Name, y=self.irr))
        self.fig_irr = go.Figure(data=data, layout=layout)
        self.fig_irr.write_html(
            os.path.join(output_folder, self.Name[0] + "irr.html"))

    def get_equity_multiple_chart(self, output_folder):

        data = []
        layout = {
            'xaxis': {
                'title': 'Project'
            },
            'yaxis': {
                'range': [0, 5],
                'title': 'Equity Multiple (#)'
            },
            'title': 'Comparison of Project Equity Multiple'
        }
        data.append(
            go.Bar(name="Equity Multiple", x=self.Name, y=self.equity_multiple))
        self.fig_equity_multiple = go.Figure(data=data, layout=layout)
        self.fig_equity_multiple.write_html(
            os.path.join(output_folder, self.Name[0] + "equity_multiple.html"))

    def get_cash_flow_return_chart(self, output_folder):

        data = []
        layout = {
            'xaxis': {
                'title': 'Project Year #'
            },
            'yaxis': {
                'title': 'Cash on Cash Return (%)'
            },
            'title': 'Comparison of Project Cash Flow Return (%)'
        }

        for proj_num in range(0, len(self.Name)):
            data.append(
                go.Bar(name=self.Name[proj_num],
                       x=self.plot_years,
                       y=self.cash_flow_return[proj_num]))

        self.fig_cash_flow_return = go.Figure(data=data, layout=layout)
        barmode = 'group'
        self.fig_cash_flow_return.update_layout(barmode=barmode)

        self.fig_cash_flow_return.write_html(
            os.path.join(output_folder, self.Name[0] + "cash_flow_return.html"))

    def get_cash_flow_chart(self, output_folder):

        for proj_num in range(0, len(self.Name)):
            data = []
            layout = {
                'xaxis': {
                    'title': 'Project'
                },
                'yaxis': {
                    'title': 'Cash Flow (USD)'
                },
                'title': 'Project Cashflows (USD)'
            }

            data.append(
                go.Bar(name='unleveraged_cash_flow',
                       x=self.plot_years,
                       y=self.unleveraged_cash_flow[proj_num]))
            data.append(
                go.Bar(name='principle_payment',
                       x=self.plot_years,
                       y=self.principle_payment[proj_num]))
            data.append(
                go.Bar(name='interest_payment',
                       x=self.plot_years,
                       y=self.interest_payment[proj_num]))
            data.append(
                go.Bar(name='leveraged_cash_flow',
                       x=self.plot_years,
                       y=self.leveraged_cash_flow[proj_num]))

            self.fig_cash_flow = go.Figure(data=data, layout=layout)
            barmode = 'group'
            self.fig_cash_flow.update_layout(barmode=barmode)

            self.fig_cash_flow.write_html(
                os.path.join(output_folder,
                             self.Name[proj_num] + "cash_flow.html"))
