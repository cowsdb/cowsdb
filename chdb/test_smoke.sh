#!/bin/bash

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

. ${DIR}/vars.sh

# test the pybind module
cd ${CHDB_DIR}

python3 -c \
    "import _chdb; res = _chdb.query('select 1112222222,555', 'JSON'); print(res)"

python3 -c \
    "import _chdb; res = _chdb.query('select 1112222222,555', 'Arrow'); print(res.bytes())"

# test the python wrapped module
cd ${PROJ_DIR}

python3 -c \
    "import chdb; res = chdb._chdb.query('select version()', 'CSV'); print(res)"

python3 -c \
    "import chdb; res = chdb.query('select version()', 'CSV'); print(res.bytes())"

# test json function
python3 -c \
    "import chdb; res = chdb.query('select isValidJSON(\'not a json\')', 'CSV'); print(res)"

# test cli
python3 -m chdb "select 1112222222,555" Dataframe
