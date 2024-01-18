#include "ProtobufListInputFormat.h"

#if USE_PROTOBUF
#   include <Core/Block.h>
#   include <Formats/FormatFactory.h>
#   include <Formats/ProtobufReader.h>
#   include <Formats/ProtobufSchemas.h>
#   include <Formats/ProtobufSerializer.h>

namespace DB
{

ProtobufListInputFormat::ProtobufListInputFormat(
    ReadBuffer & in_,
    const Block & header_,
    const Params & params_,
    const ProtobufSchemaInfo & schema_info_,
    bool flatten_google_wrappers_)
    : IRowInputFormat(header_, in_, params_)
    , reader(std::make_unique<ProtobufReader>(in_))
    , serializer(ProtobufSerializer::create(
        header_.getNames(),
        header_.getDataTypes(),
        missing_column_indices,
        *ProtobufSchemas::instance().getMessageTypeForFormatSchema(schema_info_.getSchemaInfo(), ProtobufSchemas::WithEnvelope::Yes),
        /* with_length_delimiter = */ true,
        /* with_envelope = */ true,
        flatten_google_wrappers_,
         *reader))
{
}

void ProtobufListInputFormat::setReadBuffer(ReadBuffer & in_)
{
    reader->setReadBuffer(in_);
    IRowInputFormat::setReadBuffer(in_);
}

bool ProtobufListInputFormat::readRow(MutableColumns & columns, RowReadExtension & row_read_extension)
{
    if (reader->eof())
    {
        reader->endMessage(/*ignore_errors =*/ false);
        return false;
    }

    size_t row_num = columns.empty() ? 0 : columns[0]->size();
    if (!row_num)
        serializer->setColumns(columns.data(), columns.size());

    serializer->readRow(row_num);

    row_read_extension.read_columns.clear();
    row_read_extension.read_columns.resize(columns.size(), true);
    for (size_t column_idx : missing_column_indices)
        row_read_extension.read_columns[column_idx] = false;
    return true;
}

size_t ProtobufListInputFormat::countRows(size_t max_block_size)
{
    if (getTotalRows() == 0)
        reader->startMessage(true);

    if (reader->eof())
    {
        reader->endMessage(false);
        return 0;
    }

    size_t num_rows = 0;
    while (!reader->eof() && num_rows < max_block_size)
    {
        int tag;
        reader->readFieldNumber(tag);
        reader->startNestedMessage();
        reader->endNestedMessage();
        ++num_rows;
    }

    return num_rows;
}

ProtobufListSchemaReader::ProtobufListSchemaReader(const FormatSettings & format_settings)
    : schema_info(
          format_settings.schema.format_schema,
          "Protobuf",
          true,
          format_settings.schema.is_server,
          format_settings.schema.format_schema_path)
    , skip_unsopported_fields(format_settings.protobuf.skip_fields_with_unsupported_types_in_schema_inference)
{
}

NamesAndTypesList ProtobufListSchemaReader::readSchema()
{
    const auto * message_descriptor = ProtobufSchemas::instance().getMessageTypeForFormatSchema(schema_info, ProtobufSchemas::WithEnvelope::Yes);
    return protobufSchemaToCHSchema(message_descriptor, skip_unsopported_fields);
}

void registerInputFormatProtobufList(FormatFactory & factory)
{
    factory.registerInputFormat(
            "ProtobufList",
            [](ReadBuffer &buf,
                const Block & sample,
                RowInputFormatParams params,
                const FormatSettings & settings)
            {
                return std::make_shared<ProtobufListInputFormat>(buf, sample, std::move(params),
                    ProtobufSchemaInfo(settings, "Protobuf", sample, settings.protobuf.use_autogenerated_schema), settings.protobuf.input_flatten_google_wrappers);
            });
    factory.markFormatSupportsSubsetOfColumns("ProtobufList");
    factory.registerAdditionalInfoForSchemaCacheGetter(
        "ProtobufList",
        [](const FormatSettings & settings)
        {
            return fmt::format(
                "format_schema={}, skip_fields_with_unsupported_types_in_schema_inference={}",
                settings.schema.format_schema,
                settings.protobuf.skip_fields_with_unsupported_types_in_schema_inference);
        });
}

void registerProtobufListSchemaReader(FormatFactory & factory)
{
    factory.registerExternalSchemaReader("ProtobufList", [](const FormatSettings & settings)
    {
        return std::make_shared<ProtobufListSchemaReader>(settings);
    });
}

}

#else

namespace DB
{
class FormatFactory;
void registerInputFormatProtobufList(FormatFactory &) {}
void registerProtobufListSchemaReader(FormatFactory &) {}
}

#endif