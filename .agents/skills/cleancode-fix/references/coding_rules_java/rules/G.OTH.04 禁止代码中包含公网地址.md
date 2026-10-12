# G.OTH.04 禁止代码中包含公网地址

- **规则ID**：b433ab32-fdcf-4256-8dc3-444f367e3538
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

严重

**【描述】**

secBrella告警清理指导链接:http://dfx.huawei.com/itembased/doc?ibid=SPE1000000989&navid=NVI1000072710

IP地址硬编码

**【正确示例】**

```
public void test01Good() {
    String ip = loadFromConfig();
}

```
**【错误示例】**

```
public void test01Bad() {
    /* POTENTIAL FLAW: IP地址硬编码 */
    String ip = "19.168.0.1";
}

```
**【修复建议】**

请查看告警清理指导：http://dfx.huawei.com/itembased/doc?ibid=SPE1000000989&amp&navid=NVI1000072714
