# G.LOG.01 logging模块应尽量使用懒插值的能力记录日志

- **规则ID**：f81cd666-906c-485e-aae2-595b2244b96a
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

一般

**【描述】**

logging模块具有懒插值特性：当采用logging.<logging method>(format_string, format_args)形式，logger将对日志消息中的参数字符串进行延迟插值。

因此，建议日志打印尽量采用该方式。

**【正确示例】**

```
import logging


error_details = "it is really a big bug."
error_details_ext = "Yes, really big."
logging.error("Here catch some errors, detail is:%s more:%s", error_details, error_details_ext)

```
**【错误示例】**

```
【反例1】采用logging.<logging method>(format_string % format_args)形式：
import logging


error_details = "it is really a big bug"
logging.error("Here catch some errors, detail is:%s" % error_details)

【反例2】采用format_string.format(format_args)形式：
import logging


error_details = "it is really a big bug"
logging.error("Here catch some errors, detail is:{}".format(error_details))

【反例3】
import logging


error_details = "it is really a big bug."
error_details_ext = "Yes, really big."
# POTENTIAL FLAW
logging.error(f"result is : {error_details} and {error_details_ext}")

```
**【修复建议】**

尽量使用懒插值的能力记录日志。
