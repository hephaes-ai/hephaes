import { generateStaticParamsFor, importPage } from 'nextra/pages'
import { useMDXComponents as getMDXComponents } from '../../mdx-components'

export const generateStaticParams = generateStaticParamsFor('mdxPath')

export async function generateMetadata(props: PageProps) {
  const { metadata } = await importPage(
    ((await props.params).mdxPath as string[]) || []
  )
  return metadata
}

type PageProps = {
  params: Promise<{ mdxPath?: string[] }>
}

const Wrapper = getMDXComponents().wrapper!

export default async function Page(props: PageProps) {
  const result = await importPage(
    ((await props.params).mdxPath as string[]) || []
  )
  const { default: MDXContent, toc, metadata, sourceCode } = result
  return (
    <Wrapper toc={toc} metadata={metadata} sourceCode={sourceCode}>
      <MDXContent {...props} params={await props.params} />
    </Wrapper>
  )
}
