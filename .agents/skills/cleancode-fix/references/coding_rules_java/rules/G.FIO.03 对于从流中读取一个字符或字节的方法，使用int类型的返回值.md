# G.FIO.03 对于从流中读取一个字符或字节的方法，使用int类型的返回值

- **规则ID**：5074a654-aee8-4f20-8fe2-dd5c4b46ec47
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

致命

**【描述】**

Java代码中常用的抽象方法Reader.read()方法用于从流中读取一个字节或字符，该方法会读取一个字节，返回值的范围为0～65535。 这个方法会返回一个32位的-1表示读取到流的末尾，流中已经没有可用数据。这个方法使用int来保存流结束标志及最大字节。

**【正确示例】**

```
public class CWE682_J_Rule6_4_Invalid_Read_From_Stream_01_Good {
    private static final Logger LOGGER = Logger.getLogger(CWE682_J_Rule6_4_Invalid_Read_From_Stream_01_Good.class);

    public static void readBytesFromStreamGood() {
        try (FileInputStream in = new FileInputStream("demo.txt")) {
            // Initialize stream
            int data;
            while ((data = in.read()) != -1) {
                LOGGER.info(data);
            }
        } catch (Exception e) {
            LOGGER.error("error");
        }
    }
}

```
**【错误示例】**

```
public class CWE682_J_Rule6_4_Invalid_Read_From_Stream_01_Bad {
    private static final Logger LOGGER = Logger.getLogger(CWE682_J_Rule6_4_Invalid_Read_From_Stream_01_Bad.class);

    public static void readBytesFromStreamBad() {
        try (FileInputStream in = new FileInputStream("demo.txt")) {
            // Initialize stream
            byte data;
            /* POTENTIAL FLAW: 对于从流中读取一个字符或字节的方法，使用int类型的返回值 */
            while ((data = (byte) in.read()) != -1) {
                LOGGER.info(data);
            }
        } catch (Exception e) {
            LOGGER.error("error");
        }
    }
}

```
**【修复建议】**

使用int类型的变量来保存read()的返回值，并使用该返回值判断是否读取到流的末尾，流未读完时，

将读取的内容转换为char类型。
