# G.LOG.04 非仅限于中文区销售产品禁止用中文打印日志

- **规则ID**：a780555d-79de-4f6b-87a2-1cbfe3e34d68
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

建议日志内容统一只用英文字符，避免使用中文字符，尤其是注意中文标点符号。统一日志的字符集，有利于对日志的自动化分析处理。

**【正确示例】**

```
##### 场景1： 出现用中文打印日志
- 修复示例1：用英文打印日志

  ```java
  String body = getRequestBodyData(request);
  try {
      handeData(body);
  }catch(MyBizException ex) {
      LOG.error("handle request data failed!");
  }
  ```


```
**【错误示例】**

```
##### 场景1： 出现用中文打印日志
- 错误示例：

  ```java
  String body = getRequestBodyData(request);
  try {
      handeData(body);
  }catch(MyBizException ex) {
      LOG.error("在处理请求数据时出现了异常！");
  }
  ```


```
**【修复建议】**

将日志中的中文字符、标点等替换为英文。
