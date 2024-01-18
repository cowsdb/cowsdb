#pragma once

#include "chdb.h"
#include "pybind11/pybind11.h"
#include "pybind11/pytypes.h"
#include "pybind11/stl.h"

namespace py = pybind11;

class local_result_wrapper;
class __attribute__((visibility("default"))) memoryview_wrapper;
class __attribute__((visibility("default"))) query_result;


class local_result_wrapper
{
private:
    local_result_v2 * result;

public:
    local_result_wrapper(local_result_v2 * result) : result(result) { }
    ~local_result_wrapper()
    {
        free_result_v2(result);
    }
    char * data()
    {
        if (result == nullptr)
        {
            return nullptr;
        }
        return result->buf;
    }
    size_t size()
    {
        if (result == nullptr)
        {
            return 0;
        }
        return result->len;
    }
    py::bytes bytes()
    {
        if (result == nullptr)
        {
            return py::bytes();
        }
        return py::bytes(result->buf, result->len);
    }
    py::str str()
    {
        if (result == nullptr)
        {
            return py::str();
        }
        return py::str(result->buf, result->len);
    }
    // Query statistics
    size_t rows_read()
    {
        if (result == nullptr)
        {
            return 0;
        }
        return result->rows_read;
    }
    size_t bytes_read()
    {
        if (result == nullptr)
        {
            return 0;
        }
        return result->bytes_read;
    }
    double elapsed()
    {
        if (result == nullptr)
        {
            return 0;
        }
        return result->elapsed;
    }
    bool has_error()
    {
        if (result == nullptr)
        {
            return false;
        }
        return result->error_message != nullptr;
    }
    py::str error_message()
    {
        if (has_error())
        {
            return py::str(result->error_message);
        }
        return py::str();
    }
};

class query_result
{
private:
    std::shared_ptr<local_result_wrapper> result_wrapper;

public:
    query_result(local_result_v2 * result) : result_wrapper(std::make_shared<local_result_wrapper>(result)) { }
    ~query_result() { }
    char * data() { return result_wrapper->data(); }
    py::bytes bytes() { return result_wrapper->bytes(); }
    py::str str() { return result_wrapper->str(); }
    size_t size() { return result_wrapper->size(); }
    size_t rows_read() { return result_wrapper->rows_read(); }
    size_t bytes_read() { return result_wrapper->bytes_read(); }
    double elapsed() { return result_wrapper->elapsed(); }
    bool has_error() { return result_wrapper->has_error(); }
    py::str error_message() { return result_wrapper->error_message(); }
    memoryview_wrapper * get_memview();
};

class memoryview_wrapper
{
private:
    std::shared_ptr<local_result_wrapper> result_wrapper;

public:
    memoryview_wrapper(std::shared_ptr<local_result_wrapper> result) : result_wrapper(result)
    {
        // std::cerr << "memoryview_wrapper::memoryview_wrapper" << this->result->bytes() << std::endl;
    }
    ~memoryview_wrapper() { }

    size_t size()
    {
        if (result_wrapper == nullptr)
        {
            return 0;
        }
        return result_wrapper->size();
    }

    py::bytes bytes() { return result_wrapper->bytes(); }

    void release() { }

    py::memoryview view()
    {
        if (result_wrapper != nullptr)
        {
            return py::memoryview(py::memoryview::from_memory(result_wrapper->data(), result_wrapper->size(), true));
        }
        else
        {
            return py::memoryview(py::memoryview::from_memory(nullptr, 0, true));
        }
    }
};
