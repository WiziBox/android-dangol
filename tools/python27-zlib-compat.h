/* SPDX-License-Identifier: Apache-2.0
 * Project compatibility definitions for the pinned Python 2.7.5 headers.
 * The CPython zlib module source retains its upstream license separately.
 */
#ifndef Py_SETREF
#define Py_SETREF(dst, src) do { PyObject *port_old_ref = (PyObject *)(dst); (dst) = (src); Py_DECREF(port_old_ref); } while (0)
#endif
#ifndef Py_XSETREF
#define Py_XSETREF(dst, src) do { PyObject *port_old_ref = (PyObject *)(dst); (dst) = (src); Py_XDECREF(port_old_ref); } while (0)
#endif
