# G.FMT.15 枚举常量间用逗号隔开， 换行可选

- **规则ID**：b29964eb-68ff-409f-b894-d5ef0cb7c33d
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

枚举常量间使用逗号分隔，逗号之后的换行符可选。当枚举常量间通过换行分隔时，应避免使用多个空行。

**【正确示例】**

```
```java
    public static enum EnumBlank1 {ENUM_G, ENUM_H}

    public static enum EnumBlank {
        ENUM_G,
        ENUM_H
    }

    public static enum EnumBlank {
        ENUM_G,

        ENUM_H
    }
```

```
**【错误示例】**

```
```java
    public static enum EnumBlank {
        ENUM_G,


        ENUM_H
    }
```

```
**【修复建议】**

推荐使用Huawei CodeCheck插件[https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305]的自动修复/一键格式化功能，详细使用说明见。
