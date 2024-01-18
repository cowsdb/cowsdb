#!/bin/sh

echo "Using sparse checkout for boost"

FILES_TO_CHECKOUT=$(git rev-parse --git-dir)/info/sparse-checkout
echo '/*' > $FILES_TO_CHECKOUT
echo '!/*/*' >> $FILES_TO_CHECKOUT
echo '/boost/*' > $FILES_TO_CHECKOUT
echo '!/boost/*/*' >> $FILES_TO_CHECKOUT
echo '/boost/algorithm/*' >> $FILES_TO_CHECKOUT
echo '/boost/any/*' >> $FILES_TO_CHECKOUT
echo '/boost/atomic/*' >> $FILES_TO_CHECKOUT
echo '/boost/assert/*' >> $FILES_TO_CHECKOUT
echo '/boost/bind/*' >> $FILES_TO_CHECKOUT
echo '/boost/concept/*' >> $FILES_TO_CHECKOUT
echo '/boost/config/*' >> $FILES_TO_CHECKOUT
echo '/boost/container/*' >> $FILES_TO_CHECKOUT
echo '/boost/container_hash/*' >> $FILES_TO_CHECKOUT
echo '/boost/context/*' >> $FILES_TO_CHECKOUT
echo '/boost/convert/*' >> $FILES_TO_CHECKOUT
echo '/boost/coroutine/*' >> $FILES_TO_CHECKOUT
echo '/boost/core/*' >> $FILES_TO_CHECKOUT
echo '/boost/describe/*' >> $FILES_TO_CHECKOUT
echo '/boost/detail/*' >> $FILES_TO_CHECKOUT
echo '/boost/dynamic_bitset/*' >> $FILES_TO_CHECKOUT
echo '/boost/exception/*' >> $FILES_TO_CHECKOUT
echo '/boost/filesystem/*' >> $FILES_TO_CHECKOUT
echo '/boost/functional/*' >> $FILES_TO_CHECKOUT
echo '/boost/function/*' >> $FILES_TO_CHECKOUT
echo '/boost/geometry/*' >> $FILES_TO_CHECKOUT
echo '/boost/graph/*' >> $FILES_TO_CHECKOUT
echo '/boost/heap/*' >> $FILES_TO_CHECKOUT
echo '/boost/integer/*' >> $FILES_TO_CHECKOUT
echo '/boost/intrusive/*' >> $FILES_TO_CHECKOUT
echo '/boost/iostreams/*' >> $FILES_TO_CHECKOUT
echo '/boost/io/*' >> $FILES_TO_CHECKOUT
echo '/boost/iterator/*' >> $FILES_TO_CHECKOUT
echo '/boost/math/*' >> $FILES_TO_CHECKOUT
echo '/boost/move/*' >> $FILES_TO_CHECKOUT
echo '/boost/mpl/*' >> $FILES_TO_CHECKOUT
echo '/boost/multi_index/*' >> $FILES_TO_CHECKOUT
echo '/boost/multiprecision/*' >> $FILES_TO_CHECKOUT
echo '/boost/numeric/*' >> $FILES_TO_CHECKOUT
echo '/boost/predef/*' >> $FILES_TO_CHECKOUT
echo '/boost/preprocessor/*' >> $FILES_TO_CHECKOUT
echo '/boost/program_options/*' >> $FILES_TO_CHECKOUT
echo '/boost/range/*' >> $FILES_TO_CHECKOUT
echo '/boost/regex/*' >> $FILES_TO_CHECKOUT
echo '/boost/smart_ptr/*' >> $FILES_TO_CHECKOUT
echo '/boost/type_index/*' >> $FILES_TO_CHECKOUT
echo '/boost/type_traits/*' >> $FILES_TO_CHECKOUT
echo '/boost/system/*' >> $FILES_TO_CHECKOUT
echo '/boost/tti/*' >> $FILES_TO_CHECKOUT
echo '/boost/utility/*' >> $FILES_TO_CHECKOUT
echo '/boost/lexical_cast/*' >> $FILES_TO_CHECKOUT
echo '/boost/optional/*' >> $FILES_TO_CHECKOUT
echo '/boost/property_map/*' >> $FILES_TO_CHECKOUT
echo '/boost/pending/*' >> $FILES_TO_CHECKOUT
echo '/boost/multi_array/*' >> $FILES_TO_CHECKOUT
echo '/boost/tuple/*' >> $FILES_TO_CHECKOUT
echo '/boost/icl/*' >> $FILES_TO_CHECKOUT
echo '/boost/unordered/*' >> $FILES_TO_CHECKOUT
echo '/boost/typeof/*' >> $FILES_TO_CHECKOUT
echo '/boost/parameter/*' >> $FILES_TO_CHECKOUT
echo '/boost/mp11/*' >> $FILES_TO_CHECKOUT
echo '/boost/archive/*' >> $FILES_TO_CHECKOUT
echo '/boost/function_types/*' >> $FILES_TO_CHECKOUT
echo '/boost/serialization/*' >> $FILES_TO_CHECKOUT
echo '/boost/fusion/*' >> $FILES_TO_CHECKOUT
echo '/boost/variant/*' >> $FILES_TO_CHECKOUT
echo '/boost/format/*' >> $FILES_TO_CHECKOUT
echo '/boost/locale/*' >> $FILES_TO_CHECKOUT
echo '/boost/random/*' >> $FILES_TO_CHECKOUT
echo '/boost/spirit/*' >> $FILES_TO_CHECKOUT
echo '/boost/uuid/*' >> $FILES_TO_CHECKOUT
echo '/boost/xpressive/*' >> $FILES_TO_CHECKOUT
echo '/boost/asio/*' >> $FILES_TO_CHECKOUT
echo '/boost/circular_buffer/*' >> $FILES_TO_CHECKOUT
echo '/boost/proto/*' >> $FILES_TO_CHECKOUT
echo '/boost/qvm/*' >> $FILES_TO_CHECKOUT
echo '/boost/property_tree/*' >> $FILES_TO_CHECKOUT
echo '/libs/*' >> $FILES_TO_CHECKOUT

git config core.sparsecheckout true
git checkout $1
git read-tree -mu HEAD