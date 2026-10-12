# G.LOG.01 记录日志应该使用Facade模式的日志框架

- **规则ID**：63a2314e-9143-4e0d-8041-6caa07106af3
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

专用日志工具与控制台打印（System.out、System.err）相比，提供了更丰富的日志记录功能，且使用更加简单。日志打印推荐使用Facade模式的日志框架，如第三方slf4j、产品自研日志框架等，不要使用System.out与System.err进行控制台打印。

**【正确示例】**

```
```java
long start = System.currentTimeMillis();
LOGGER.info("items loaded, use {}ms.", (System.currentTimeMillis() - start));
```

```
**【错误示例】**

```
```java
long start = System.currentTimeMillis();
System.out.println ("items loaded, use " + (System.currentTimeMillis() - start) + "ms.");
```

```
**【修复建议】**

将System.out与System.err等方法替换为专用日志工具。
