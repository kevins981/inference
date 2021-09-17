"""
Tool to generate the final results speadsheet from the checker csv output.
The resulting excel files can be imported into google sheets.
"""
import argparse
import os
import sys
import re
import numpy as np
import pandas as pd


def get_args():
  """Parse commandline."""
  parser = argparse.ArgumentParser()
  parser.add_argument("--input", required=True,
                      help="results csv from checker")
  args = parser.parse_args()
  return args


def main():
  args = get_args()

  df = pd.read_csv(args.input).fillna("")

  # rename some fields
  df.rename(
      columns={
          "Organization": "Submitter",
          "Division": "Category",
          "SystemType": "Suite",
          "SystemName": "System",
          "host_processor_model_name": "Processor",
          "accelerator_model_name": "Accelerator",
          "accelerators_per_node": "a#",
          "notes": "Notes",
          'framework': 'Software',
      },
      inplace=True)
  df.rename(columns={"Model": "UsedModel"}, inplace=True)
  df.rename(columns={"MlperfModel": "Model"}, inplace=True)

  # fix issues with raw data
  df['host_processor_core_count'] = df['host_processor_core_count'].apply(lambda x: 2 if x == '2 (big); 4 (LITTLE)' else x)
  df['Availability'] = df['Availability'].apply(lambda x: "available" if x == 'on-premise' else x)

  # cleanup counts
  df['Accelerator'] = df['Accelerator'].apply(lambda x: x if x != "-" else "")
  df['a#'] = df['a#'].apply(lambda x: int(x) if x != "" else 0)
  df['a#'] = df['a#'].apply(lambda x: x if x > 0 else "")
  df['p#'] = df.apply(lambda x: int(x['host_processors_per_node']) * int(x['number_of_nodes']), axis=1)

  # details url
  base_url = "https://github.com/mlcommons/submissions_inference_1_1/tree/master"
  df['Details'] = df.apply(
      lambda x: '=HYPERLINK("{}","details")'.format("/".join([base_url, x['Category'], x['Submitter'], "results", x['Platform']])), axis=1)

  output = args.input[:-4]
  writer = pd.ExcelWriter(output + '.xlsx', engine='xlsxwriter')

  index = [
      'ID',
      'Unique ID (e.g. for Audit)',
      'Submitter',
      'Availability',
      'System',
      'Processor',
      'p#',
      'Accelerator',
      'a#',
      'Software',
      'Notes',
      'Details',
  ]
  columns = [
      'Model',
      'Scenario',
      'Units',
  ]
  columns_order = [
    [
      'Result'
    ],

    [
      'resnet',
      'ssd-small',
      'ssd-large',
      '3d-unet-99',
      '3d-unet-99.9',
      'rnnt',
      'bert-99',
      'bert-99.9',
      'dlrm-99',
      'dlrm-99.9'
    ],

    [
      'SingleStream',
      'MultiStream',
      'Server',
      'Offline'
    ],
    
    [
      'Latency (ms)',
      'Streams',
      'Samples/s',
      'Queries/s',
      'Joules',
      'Joules/Stream',
      'Watts',
    ]
  ]

  def MakeWorksheet(df, filter_dict, sheet_name):
    for key, value in filter_dict.items():
      df = df[value(df[key])]
    df = df.pivot_table(index=index, columns=columns, values=['Result'])
    df = df.fillna('')
    if df.size == 0:
      return
    for i, order in enumerate(columns_order):
      df = df.reindex(columns = order, level = i)
    df.to_excel(writer, sheet_name=sheet_name)

  def Equal(x):
    return lambda y: y == x

  def NotEqual(x):
    return lambda y: y != x

  def And(x, y):
    return lambda z: x(z) & y(z)

  def MakeUniqueID(x):
    key_list = ['Suite', 'Category', 'Submitter', 'Platform']
    if x['Category'] == 'open':
      key_list.append('UsedModel')
    return '/'.join(x[key_list])

  df['Unique ID (e.g. for Audit)'] = df.apply(MakeUniqueID, axis=1)
  df.sort_values(
      by=[
          'Category', 'Suite', 'Availability', 'Submitter',
          'Unique ID (e.g. for Audit)'
      ],
      inplace=True)
  id_dict = {
      key: 1 + value
      for (value,
           key) in enumerate(pd.unique(df['Unique ID (e.g. for Audit)']))
  }
  df['ID'] = df.apply(
      lambda x: '1.1-{:03}'.format(id_dict[x['Unique ID (e.g. for Audit)']]),
      axis=1)

  for suite in ['closed', 'open']:
    for scenario in ['datacenter', 'edge']:
      MakeWorksheet(
          df, {
              'Category': Equal(suite),
              'Suite': Equal(scenario),
              'Units': And(And(NotEqual('Watts'), NotEqual('Joules')), NotEqual('Joules/Stream'))
          }, suite + ',' + scenario)

      MakeWorksheet(
          df, {
              'Category': Equal(suite),
              'Suite': Equal(scenario),
              'has_power': Equal(True)
          }, suite + ',' + scenario + ',power')

  score_format = writer.book.add_format({'num_format': '#,##0.00'})
  bg_format = writer.book.add_format({'bg_color': '#efefef'})
  for ws in writer.book.worksheets():
    ws.set_column(1, 1, None, None, {'hidden': 1})
    ws.set_column(len(index), 100, None, score_format)
    ws.conditional_format(
        2 + len(columns), 0, 200, 100, {
            'type':
                'formula',
            'criteria':
                '=mod(countunique($c$' + str(len(columns) + 3) + ':$c' +
                str(len(columns) + 3) + '), 2) = 0',
            'format':
                bg_format,
        })

  writer.save()

  return 0


if __name__ == "__main__":
  sys.exit(main())
