# G.LOG.02 日志工具Logger类的实例必须声明为private static final或者private final

- **规则ID**：3a671bf8-69b4-426e-a03d-3921bd847fee
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

对于工具类的实例，如果声明时并进行了初始化，应该声明为private static final，如果只是声明但未初始化，则应声明为private final。



- 声明为private是出于访问封装的考虑，防止Logger类的实例对象被其他类非法使用；

- 声明为static是为了防止重复new出Logger类的实例，造成资源的浪费，同时防止实例被序列化，造成安全风险（精心设计的library除外）；

- 声明为final是因为在类的生命周期内无需变更Logger类的实例。

**【正确示例】**

```
##### 场景1：
- 修复示例：
```java
private static final Logger logger = LoggerFactory.getLogger(CheckUpdateToAutoRenewStep.class);
```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：没有使用final修饰日志实例
```java
private static Logger logger = LoggerFactory.getLogger(CheckUpdateToAutoRenewStep.class);
```


```
**【修复建议】**

日志工具实例，应该声明为`private static final`或`private final`。
