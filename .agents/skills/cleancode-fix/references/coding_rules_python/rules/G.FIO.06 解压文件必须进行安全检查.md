# G.FIO.06 解压文件必须进行安全检查

- **规则ID**：522380ea-895c-44d6-8b09-7018637f88ed
- **更新时间**：2026-04-07 04:15:04

---

**【问题级别】**

一般

**【描述】**

攻击者有可能上传一个很小的zip文件，但是完全解压缩之后达到几百万GB甚至更多，消耗完磁盘空间导致系统或程序无法正常运行。因此在解压缩文件时需要限制所使用的磁盘空间。

因此，禁止直接一次性递归解压压缩包全部内容，在解压前最少进行以下几点基础安全检查：

1.文件个数是否超出业务预期个数；

2.文件大小是否超出业务预期大小；

3.文件大小是否超出目标目录所在磁盘空间。



建议根据需要，依赖其它工程手段加强防范，这些工程手段包括并不限于：

1.为解压文件单独分区，限定大小；

2.对压缩包做健康检查，包括其中内容是否符合业务预期；

3.对CPU和内存的使用量进行限定，防止大量压缩包中海量小文件等攻击手段。（需结合程序实际运行情况估计，慎用）



以上几点建议非强制执行，正例中展示的是常用的校验方法，不能规避所有问题。

具体问题还需要结合产品特点具体分析，最终使解压后的文件大小在可控范围内。

**【正确示例】**

```
import os
import zipfile
import psutil


class MyZip:
    # 限制解压后大小不能超过1M，文件个数不能超过10个
    MAX_SIZE = 1 * 1024 * 1024
    MAX_FILE_CNT = 10

    @staticmethod
    def unzip(path, zip_file):
        file_path = path + os.sep + zip_file
        dest_dir = path
        src_file = zipfile.ZipFile(file_path, 'r')

        # 检查点1：检查文件个数，文件个数大于预期值时上报异常退出
        file_count = len(src_file.infolist())
        if file_count >= MyZip.MAX_FILE_CNT:
            raise IOError(f'zipfile({zip_file}) contains {file_count} files exceed max file count')

        # 检查点2：检查第一层解压文件总大小，总大小超过设定的上限值
        total_size = sum(info.file_size for info in src_file.infolist())
        if total_size >= MyZip.MAX_SIZE:
            raise IOError(f'zipfile({zip_file}) size({total_size}) exceed max limit')

        # 检查点3：检查第一层解压文件总大小，总大小超过磁盘剩余空间
        dest_dir_partition = '/'  # 解压目录所在分区
        if total_size >= psutil.disk_usage(dest_dir_partition).free:
            raise IOError(f'zipfile({zip_file}) size({total_size}) exceed remain target disk space')

        # 所有检查通过之后，解压所有文件
        src_file.extractall(dest_dir)

```
**【错误示例】**

```


```
**【修复建议】**
