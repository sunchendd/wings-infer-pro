# SecJ_Zip_Entry_Size

- **规则ID**：a003058d-5f49-4dca-9975-20b8f4560d66
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

从java.util.zip.ZipInputStream中解压文件时，zip压缩算法可能有很大的压缩比，可以把超大文件压缩成很小的zip文件（例如可以将上G的文件压缩为几K大小），这样的文件解压可能会导致zip炸弹（zip bomb）攻击。所以zip文件解压时，要对解压的实际文件大小进行检查，若解压之后的文件大小超过一定的限制，必须拒绝解压。具体的大小限制根据实际情况来确定。除此之外，解压时，还需要对解压出来的文件数量进行限制，防止zip压缩包中是数量巨大的小文件。

**【正确示例】**

```
```java

public class CWE409_J_Rule1_7_Zip_Entry_Size_Good {

static final int BUFFER = 512;

static final int TOOBIG = 0x6400000; // max size of unzipped data, 100MB

static final int TOOMANY = 1024; // max number of files



// ...

// The code validates the name of each entry before extracting the entry.

// If the name is invalid, the entire extraction is aborted.

private String sanitizeFileName(String entryName, String intendedDir) throws IOException {

File f = new File(intendedDir, entryName);

String canonicalPath = f.getCanonicalPath();

File iD = new File(intendedDir);

String canonicalID = iD.getCanonicalPath();

if (canonicalPath.startsWith(canonicalID)) {

return canonicalPath;

} else {

throw new IllegalStateException("File is outside extraction target directory.");

}

}



public final void unzip_compilant(String fileName, String destDir) throws java.io.IOException {

FileInputStream fis = new FileInputStream(fileName);

ZipInputStream zis = new ZipInputStream(new BufferedInputStream(fis));

ZipEntry entry;

int total = 0;

int entries = 0;

try {

while ((entry = zis.getNextEntry()) != null) {

BufferedOutputStream dest = null;

int count;

byte data[] = new byte[BUFFER];

// Write the files to the disk, but ensure that the entryName is valid,and that the file is not insanely big

String name = sanitizeFileName(entry.getName(), destDir);

// process file

FileOutputStream fos = new FileOutputStream(name);

dest = new BufferedOutputStream(fos, BUFFER);

/*【GOOD】 通过循环获取文件大小 */

while ((count = zis.read(data, 0, BUFFER)) != -1) {

total += count;

if (total > TOOBIG) {

break;

}

dest.write(data, 0, count);

}

entries++;

// if the total number of entry is larger than the max number,it will throw exception.

if (entries > TOOMANY) {

//handle exception

}

// if the total size of zip file is bigger than the max size value,it will throw exception.

if (total > TOOBIG) {

//handle exception

}

// …

}

} finally {

zis.close();

}

}

}

```

```
**【错误示例】**

```
```java

public class CWE409_J_Rule1_7_Zip_Entry_Size_Bad {

public static final int BUFFER = 512;

public static final int TOOBIG = 0x6400000; // 100MB



public final void test01Bad(String filename) throws java.io.IOException {

FileInputStream fis = new FileInputStream(filename);

ZipInputStream zis = new ZipInputStream(new BufferedInputStream(fis));

ZipEntry entry;

try {

while ((entry = zis.getNextEntry()) != null) {

System.out.println("Extracting: " + entry);

int count;

byte data[] = new byte[BUFFER];

// Write the files to the disk, but only if the file is not

// insanely big

int a = (int) entry.getSize();

/* 【不符合】: if语句中使用ZipEntry.getSize()来做文件大小的判断。 */

if (a > TOOBIG) {

throw new IllegalStateException("File to be unzipped is huge.");

}

/* 【不符合】: if语句中使用ZipEntry.getSize()来做文件大小的判断。 */

if (entry.getSize() == -1) {

throw new IllegalStateException("File to be unzipped might be huge.");

}

FileOutputStream fos = new FileOutputStream(entry.getName());

BufferedOutputStream dest = new BufferedOutputStream(fos, BUFFER);

while ((count = zis.read(data, 0, BUFFER)) != -1) {

dest.write(data, 0, count);

}

dest.flush();

dest.close();

zis.closeEntry();

}

} finally {

zis.close();

}

}

}

```

```
**【修复建议】**

在解压每个文件之前对其文件名进行校验，如果校验失败，终止整个解压过程；不要使用ZipEntry.getSize统计大小，边读边统计实际解压出的文件总大小，如果达到指定的阈值，抛出异常终止解压操作；统计解压出来的文件的数量，如果达到指定阈值，会抛出异常终止解压操作。
