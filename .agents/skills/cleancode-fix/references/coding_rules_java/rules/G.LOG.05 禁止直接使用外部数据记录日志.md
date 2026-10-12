# G.LOG.05 禁止直接使用外部数据记录日志

- **规则ID**：f1324bc4-28ae-492d-b7e5-98ed3c848e6b
- **更新时间**：2026-04-07 04:00:05

---

**【问题级别】**

严重

**【描述】**

secBrella告警清理指导链接:http://dfx.huawei.com/itembased/doc?ibid=SPE1000000989&navid=NVI1000072710

将官方规则中已知的告警点规则重写，要求带有污染标识HW_CSPL_JAVA_LOG_FORGING且不带有校验后的标识VALIDATED_HW_CSPL_JAVA_LOG_FORGING则告警。 产品可以更具自身需要，定制污染源规则和清理规则。

**【正确示例】**

```
public String replaceCRLF(String message) {
    if (message == null) {
        return "";
    }
    return message.replace('
', '_').replace('\r', '_');
}
外部数据记录到日志中前，将其中的\r
等导致换行的字符进行替换，消除注入风险。上述示例为其中一种实现方式。

```
**【错误示例】**

```
String data;

data = ""; /* Initialize data */


/* Read data from cookies */
{
    Cookie cookieSources[] = request.getCookies();
    if (cookieSources != null) {
        data = cookieSources[0].getValue();
    }
}


/* POTENTIAL FLAW: log injection debug */
LOGGER.debug(data);

```
**【修复建议】**

请查看告警清理指导：http://dfx.huawei.com/itembased/doc?ibid=SPE1000000989&amp&navid=NVI1000072714
