# G.LOG.03 日志必须分等级

- **规则ID**：4ee9c1ae-682a-4c44-bd47-02efa98d9947
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

如果日志不分等级，则定位问题时，无法快速有效屏蔽大量低级别信息，给快速定位带来难度。



日志可分为以下级别：trace（有的也叫verbose）、debug、info、warning、error、fatal。

**【正确示例】**

```
##### 场景1： 对于info及以下级别的日志，应该避免直接进行日志内容拼接
- 修复示例：对info及以下级别的日志，使用条件形式或占位符的方式进行日志内容的构造

  ```java
  // 如果日志库提供了带"msgSupplier"的API，如下这样调用可以消除不必要的消息创建
  LOGGER.debug(() ->
      "Processing trade with id: " + id + " and symbol: " + symbol.fetchBigMessage());

  // 采用条件方式
  if (LOGGER.isDebugEnabled()) {
      LOGGER.debug("Processing trade with id: " + id + " and symbol: " + symbol);
  }

  // 或者使用占位符
  LOGGER.debug("Processing trade with id: {} and symbol: {}" , id, symbol);
  ```


```
**【错误示例】**

```
##### 场景1： 对于info及以下级别的日志，应该避免直接进行日志内容拼接
- 错误示例：对info及以下级别的日志，直接进行字符串拼接

  ```java
  LOGGER.debug("Processing trade with id: " + id + " and symbol: " + symbol);
  ```


```
**【修复建议】**

推荐与具体实现有关的日志记录trace或debug级，一般的业务处理日志用info级，不影响业务进行的错误用warning级，例如用户输入参数错误。而error或fatal级，只记录系统逻辑出错、异常或者重要的错误信息，常常向运维系统报警。



建议生产环境不输出trace或debug日志；有选择地输出info日志；输出warning、error、fatal日志。



对info及以下级别的日志，应使用条件形式或占位符的方式进行输出。
